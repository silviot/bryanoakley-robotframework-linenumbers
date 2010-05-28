# Automatically generated by 'package.py' script.
import sys


VERSION = 'trunk'
RELEASE = '20100528'
TIMESTAMP = '20100528-143734'

def get_version(sep=' '):
    if RELEASE == 'final':
        return VERSION
    return VERSION + sep + RELEASE

def get_full_version(who=''):
    interpreter   =  sys.platform.startswith('java') and 'Jython' or 'Python'
    syversion = sys.version.split()[0]
    vers = '%s %s (%s %s on %s)' % (who, get_version(), interpreter, 
                                         syversion, sys.platform)
    return vers.strip()

if __name__ == '__main__':
    print get_version(*sys.argv[1:])
