#  Copyright 2008-2011 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from time import time

import zlib
import base64

from robot import utils


class _Handler(object):

    def __init__(self, context, *args):
        self._context = context
        self._data_from_children = []
        self._handlers = {
            'robot'      : _RobotHandler,
            'suite'      : _SuiteHandler,
            'test'       : _TestHandler,
            'statistics' : _StatisticsHandler,
            'stat'       : _StatItemHandler,
            'errors'     : _Handler,
            'doc'        : _TextHandler,
            'kw'         : _KeywordHandler,
            'arg'        : _ArgumentHandler,
            'arguments'  : _ArgumentsHandler,
            'tag'        : _TextHandler,
            'tags'       : _Handler,
            'msg'        : _MsgHandler,
            'status'     : _StatusHandler,
            'metadata'   : _MetadataHandler,
            'item'       : _MetadataItemHandler,
            }

    def get_handler_for(self, name, attrs):
        return self._handlers[name](self._context, attrs)

    def add_child_data(self, data):
        self._data_from_children.append(data)

    def end_element(self, text):
        return self._data_from_children


class RootHandler(_Handler):
    # TODO: Combine _RootHandler and _RobotHandler

    @property
    def data(self):
        return self._data_from_children[0]


class _RobotHandler(_Handler):

    def __init__(self, context, attrs):
        _Handler.__init__(self, context, attrs)
        self._generator = attrs.getValue('generator')

    def end_element(self, text):
        return {'generator': self._generator,
                'suite': self._data_from_children[0],
                'stats': self._data_from_children[1],
                'errors': self._data_from_children[2],
                'baseMillis': self._context.basemillis,
                'strings': self._context.dump_texts()}


class _SuiteHandler(_Handler):

    def __init__(self, context, attrs):
        _Handler.__init__(self, context, attrs)
        self._name = attrs.getValue('name')
        self._source = attrs.get('source') or ''
        self._context.start_suite(self._name)
        self._context.collect_stats()

    def end_element(self, text):
        result = ['suite', self._source, self._name] + self._data_from_children + [self._context.dump_stats()]
        self._context.end_suite()
        return result


class _TestHandler(_Handler):

    def __init__(self, context, attrs):
        _Handler.__init__(self, context, attrs)
        name = attrs.getValue('name')
        self._name_id = self._context.get_text_id(name)
        self._timeout = self._context.get_text_id(attrs.get('timeout'))
        self._context.start_test(name)

    def get_handler_for(self, name, attrs):
        if name == 'status':
            # TODO: Use 1/0 instead of Y/N. Possibly also 1/0/-1 instead of P/F/N.
            self._critical = 'Y' if attrs.get('critical') == 'yes' else 'N'
        return _Handler.get_handler_for(self, name, attrs)

    def end_element(self, text):
        result = ['test', self._name_id, self._timeout, self._critical] + self._data_from_children
        self._context.add_test(self._critical == 'Y', result[-1][0] == 'P')
        self._context.end_test()
        return result


class _KeywordHandler(_Handler):

    def __init__(self, context, attrs):
        _Handler.__init__(self, context, attrs)
        self._context.start_keyword()
        self._type = attrs.getValue('type')
        self._name = self._context.get_text_id(attrs.getValue('name'))
        self._timeout = self._context.get_text_id(attrs.getValue('timeout'))

    def end_element(self, text):
        if self._type == 'teardown' and self._data_from_children[-1][0] == 'F':
            self._context.teardown_failed()
        self._context.end_keyword()
        return [self._type, self._name, self._timeout] + self._data_from_children


class _StatisticsHandler(_Handler):

    def get_handler_for(self, name, attrs):
        return _Handler(self._context, attrs)


class _StatItemHandler(_Handler):

    def __init__(self, context, attrs):
        _Handler.__init__(self, context, attrs)
        self._pass = int(attrs.getValue('pass'))
        self._fail = int(attrs.getValue('fail'))
        self._doc = attrs.get('doc', '')
        self._info = attrs.get('info', '')
        self._links = attrs.get('links', '')
        self._pattern = attrs.get('combined', '')

    def end_element(self, text):
        return [text, self._pass, self._fail, self._doc, self._info,
                self._links, self._pattern]


class _StatusHandler(object):
    def __init__(self, context, attrs):
        self._context = context
        self._status = attrs.getValue('status')[0]
        self._starttime = self._context.timestamp(attrs.getValue('starttime'))
        endtime = self._context.timestamp(attrs.getValue('endtime'))
        self._elapsed = self._calculate_elapsed(endtime)

    def _calculate_elapsed(self, endtime):
        # Both start and end may be 0 so must compare against None
        if self._starttime is None or endtime is None:
            return None
        return endtime - self._starttime

    def end_element(self, text):
        result = [self._status,
                  self._starttime,
                  self._elapsed]
        if text:
            result += [self._context.get_text_id(text)]
        return result


class _ArgumentHandler(_Handler):

    def end_element(self, text):
        return text


class _ArgumentsHandler(_Handler):

    def end_element(self, text):
        return self._context.get_text_id(', '.join(self._data_from_children))


class _TextHandler(_Handler):

    def end_element(self, text):
        return self._context.get_text_id(text)


class _MetadataHandler(_Handler):

    def __init__(self, context, attrs):
        _Handler.__init__(self, context, attrs)
        self._metadata = {}

    def add_child_data(self, data):
        self._metadata[data[0]] = data[1]

    def end_element(self, text):
        return self._metadata


class _MetadataItemHandler(_Handler):

    def __init__(self, context, attrs):
        _Handler.__init__(self, context, attrs)
        self._name = attrs.getValue('name')

    def end_element(self, text):
        return [self._name, self._context.get_text_id(text)]


class _MsgHandler(object):

    def __init__(self, context, attrs):
        self._context = context
        self._msg = [self._context.timestamp(attrs.getValue('timestamp')),
                     attrs.getValue('level')[0]]
        self._is_html = attrs.get('html')
        self._is_linkable = attrs.get("linkable") == "yes"

    def end_element(self, text):
        self._add_text(text)
        self._handle_warning_linking()
        return self._msg

    def _handle_warning_linking(self):
        if self._is_linkable:
            self._msg += [self._context.link_to(self._msg)]
        elif self._msg[1] == 'W':
            self._context.create_link_to_current_location(self._msg)

    def _add_text(self, text):
        if self._is_html:
            self._msg += [self._context.get_text_id(text)]
        else:
            self._msg += [self._context.get_text_id(utils.html_escape(text, replace_whitespace=False))]

class Context(object):

    def __init__(self):
        self._texts = TextCache()
        self._basemillis = 0
        self._stats = Stats()
        self._current_place = []
        self._kw_index = []
        self._links = {}

    @property
    def basemillis(self):
        return self._basemillis

    def collect_stats(self):
        self._stats = self._stats.new_child()
        return self

    def dump_stats(self):
        try:
            return self._stats.dump()
        finally:
            self._stats = self._stats.parent

    def get_text_id(self, text):
        return self._texts.add(text)

    def dump_texts(self):
        return self._texts.dump()

    def timestamp(self, time):
        if time == 'N/A':
            return None
        millis = int(utils.timestamp_to_secs(time, millis=True) * 1000)
        if not self._basemillis:
            self._basemillis = millis
        return millis - self.basemillis

    def start_suite(self, name):
        self._current_place += [('suite', name)]
        self._kw_index += [0]

    def end_suite(self):
        self._current_place.pop()
        self._kw_index.pop()

    def start_test(self, name):
        self._current_place += [('test', name)]
        self._kw_index += [0]

    def end_test(self):
        self._current_place.pop()
        self._kw_index.pop()

    def start_keyword(self):
        self._current_place += [('keyword', self._kw_index[-1])]
        self._kw_index[-1] += 1
        self._kw_index += [0]

    def end_keyword(self):
        self._current_place.pop()
        self._kw_index.pop()

    def create_link_to_current_location(self, key):
        self._links[tuple(key)] = self._create_link()

    def _create_link(self):
        return "keyword_"+".".join(str(v) for _, v in self._current_place)

    def link_to(self, key):
        return self._links[tuple(key)]

    def add_test(self, critical, passed):
        self._stats.add_test(critical, passed)

    def teardown_failed(self):
        self._stats.fail_all()


class Stats(object):
    TOTAL = 0
    TOTAL_PASSED = 1
    CRITICAL = 2
    CRITICAL_PASSED = 3

    def __init__(self, parent=None):
        self.parent = parent
        self._stats = [0,0,0,0]
        self._children = []

    def new_child(self):
        self._children += [Stats(self)]
        return self._children[-1]

    def add_test(self, critical, passed):
        self._stats[Stats.TOTAL] += 1
        if passed:
            self._stats[Stats.TOTAL_PASSED] +=1
        if critical:
            self._stats[Stats.CRITICAL] += 1
            if passed:
                self._stats[Stats.CRITICAL_PASSED] += 1

    def dump(self):
        if self.parent:
            for i in range(4):
                self.parent._stats[i] += self._stats[i]
        return self._stats

    def fail_all(self):
        self._stats[1] = 0
        self._stats[3] = 0
        for child in self._children:
            child.fail_all()


class TextIndex(int):
    """
    Marker class for identifying that the number in question is a text index
    """

ZERO_INDEX = TextIndex(0)


class TextCache(object):
    # TODO: Tune compressing thresholds
    _compress_threshold = 20
    _use_compressed_threshold = 1.1

    def __init__(self):
        self.texts = {}
        self.index = 1

    def add(self, text):
        if not text:
            return ZERO_INDEX
        text = self._encode(text)
        if text not in self.texts:
            self.texts[text] = TextIndex(self.index)
            self.index += 1
        return self.texts[text]

    def _encode(self, text):
        raw = self._raw(text)
        if raw in self.texts or len(raw) < self._compress_threshold:
            return raw
        compressed = base64.b64encode(zlib.compress(text.encode('UTF-8'), 9))
        if len(raw) * self._use_compressed_threshold > len(compressed):
            return compressed
        return raw

    def _raw(self, text):
        return '*'+text

    def dump(self):
        l = range(len(self.texts)+1)
        l[0] = '*'
        for k, v in self.texts.items():
            l[v] = k
        return l
