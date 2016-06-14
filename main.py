#!/usr/bin/env python
# -*- coding: utf-8 -*-
# author hwlin 20160128

import os
import datetime
import sys
import argparse
import pycurl
import StringIO
import re

logfile = None
verbose = False

def log(string):
    if logfile is None:
        print('log error!')
        exit(1)
    date = datetime.datetime.now().strftime("%H:%M:%S")
    if verbose == True: print('[%s] %s' % (date, string))
    logfile.write('[%s] %s\n' % (date, string))

def get_args():
    global verbose
    parser = argparse.ArgumentParser(description='This is a simple crawler.')
    parser.add_argument('-u', '--url', action='append', help='start urls', dest='urls', required=True)
    parser.add_argument('-d', '--domain', action='append', help='allow domains', dest='domains', required=True)
    parser.add_argument('-f', '--filter-endswith', action='append', help='filter url(endswith)', dest='filtere')
    parser.add_argument('-F', '--filter-contain', action='append', help='filter url(contain)', dest='filterc')
    parser.add_argument('-t', '--fetch-timeout', type=int, default=5, help='fetching file timeout', dest='ftime')
    parser.add_argument('-T', '--connection-timeout', type=int, default=2, help='connection timeout', dest='ctime')
    parser.add_argument('-l', '--url-length', type=int, default=128, help='url max length', dest='urllen')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose', dest='verbose')
    parser.add_argument('-w', '--write-dir', help='write directory', dest='writedir')
    return parser.parse_args(sys.argv[1:])

def main():
    global logfile, verbose
    # parse args
    args = get_args()
    if args.verbose == True:
        verbose = True
    if args.writedir is not None and os.path.isdir(args.writedir) == False:
        os.mkdir(args.writedir)

    # log start
    logfile = open('crawler.log', 'w')
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log('crawler start at: %s' % (date))

    # setting variables
    urls = args.urls
    filtere = []
    filterc = []
    if args.filtere is not None:
        filtere = filtere + args.filtere
    if args.filterc is not None:
        filterc = filterc + args.filterc
    urllen = args.urllen
    domains = []
    if args.domains is not None:
        for domain in args.domains:
            pattern = '^http[s]?://' + domain
            try:
                regex = re.compile(pattern)
            except:
                log('domain regex compile failed: %s' % (pattern))
                exit(1)
            domains.append(regex)

    # prepare curl
    buffer = StringIO.StringIO()
    header = StringIO.StringIO()
    curl = pycurl.Curl()
    curl.setopt(curl.WRITEDATA, buffer)
    curl.setopt(curl.HEADERFUNCTION, header.write)
    curl.setopt(pycurl.CONNECTTIMEOUT, args.ctime)
    curl.setopt(pycurl.TIMEOUT, args.ftime)
    #curl.setopt(pycurl.FOLLOWLOCATION, True)
    i = 0
    cols = []

    for url in urls:
        # prevent http://www.cs.ccu.edu.tw <- not endwith /
        if re.match('http[s]?://[^/]*$', url):
            url = url + '/'
        log('curl(%d): %s' % (i, url))
        curl.setopt(curl.URL, url)
        buffer.truncate(0)
        header.truncate(0)

        # catch timeout or interrupt
        try:
            curl.perform()
        except KeyboardInterrupt:
            log('user interrupt')
            exit(1) # interrupt
        except pycurl.error as e:
            if e[0] == 23:
                log('user interrupt')
                exit(1) # interrupt
            log('timeout error: %.2f s' % (curl.getinfo(pycurl.TOTAL_TIME)))
            continue

        # handle HTTP_CODE
        code = curl.getinfo(pycurl.HTTP_CODE)
        if code == 200:
            body = buffer.getvalue()
            results = re.findall('(?:href|src|action)=["\'](.*?)["\']', body)
            mails = re.findall('[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', body)
        elif code in (301, 302):
            body = header.getvalue()
            results = re.findall('[Ll]ocation: ([^\r]*)', body)
            mails = ()
        else:
            log('return code error: %d' % (code))
            continue

        # print mails
        for m in mails:
            if m not in cols:
                log(m)
                if verbose == False: print m
            cols.append(m)

        # writing file
        if args.writedir is not None:
            # prepare writing file
            try:
                fn = args.writedir + '/' + re.findall('http[s]?://(.*?/.*)', url)[0]
                if fn.find('?') != -1:
                    fn = fn[0:fn.find('?')] + re.sub('/', '%2f', fn[fn.find('?'):])
            except:
                log('fn error: %s' % (url))
                continue
            if os.path.isdir(fn) or fn.endswith('/') or fn.endswith('/.') or fn.endswith('/..'):
                if fn.endswith('/') == False:
                    fn = fn + '/'
                fn = fn + 'index'
            dir = re.findall('((?:[^?]*?/)+[^/?]*)/', fn)[0]

            # if dir is a file
            if os.path.isfile(dir) == True:
                log('moving %s' % (dir))
                try:
                    os.rename(dir, args.writedir + '/crawler.tmp')
                    os.makedirs(dir)
                    os.rename(args.writedir + '/crawler.tmp', dir + '/index')
                except:
                    log('moving error: %s' % (dir))

            # if dir not exist
            if os.path.isdir(dir) == False:
                try: os.makedirs(dir)
                except:
                    log('mkdir error: %s' % (dir))

            # write file
            try:
                file = open(fn, 'w')
                file.write(body)
                file.close()
            except:
                log('writing file error: %s' % (fn))

        i = i + 1

        # handle new URLs
        for result in results:
            #check url
            try:
                result = result.strip()
                if result == '':
                    continue
                elif result.startswith('#'):
                    continue
                elif result.startswith('mailto'):
                    continue
                elif result.startswith('javascript'):
                    continue
                elif len(result) > urllen:
                    continue
                elif result.startswith('http'):
                    result = result
                elif result.startswith('//'):
                    result = 'http:' + result
                elif result.startswith('/'):
                    result = re.findall('(http[s]?://.*?)/', url)[0] + result
                else:
                    result = re.findall('http[s]?://(?:[^?]*?/)+', url)[0] + result
            except:
                log('regex error: %s' % (result))
                continue
            # combine ../ or ./
            result = re.sub('/[^&?]*?/../', '/', result)
            result = re.sub('/./', '/', result)
            result = re.sub(' ', '%20', result)
            if result in urls:
                continue
            # check filetype
            filtered = False
            for filter in filtere:
                if result.endswith(filter):
                    filtered = True
                    break
            if filtered == True:
                continue
            for filter in filterc:
                if result.find(filter) != -1:
                    filtered = True
                    break
            if filtered == True:
                continue
            # check allow domain
            for domain in domains:
                if domain.search(result):
                    urls.append(result)
                    break
    curl.close()
    log('crawler iinished at %s' % (date))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print""
        exit(1)
