from scraper import PastebinComScraper
from storage import SQLite3Storage, FlatFileStorage
import argparse
import time
import sys
import os
import sqlite3

session_trending_count = 0
session_pastes_count = 0

def parse_args():
    parser = argparse.ArgumentParser(description='Pastebin mirror tool. Save publicly '\
                                     'uploaded pastes in real-time to an SQLite database'\
                                     ' or as flat text files. Optionally archive trending'\
                                     ' pastes as well.')
    parser.add_argument('-o', '--output', type=str, required=True, 
                        help='output SQLite database file or directory name if '\
                        '--output-format=flat-file')
    parser.add_argument('-f', '--output-format', dest='output_format', choices=['sqlite', 'flat-file'], 
                        default='sqlite', help='output format')
    parser.add_argument('-r', '--rate', type=int, default=30,
                        help='seconds between requests to the pastebin scrape API. minimum 1 second.')
    parser.add_argument('-t', '--trending', dest='trending', action='store_true', 
                        default=False, help='archive trending pastes (runs once per hour)')
    parser.add_argument('-m', '--mirror', dest='mirror', action='store_true',
                        help='archive pastebin in real-time using the scrape API. '\
                        'Requires a PRO LIFETIME account to whitelist your IP address.')
    parser.add_argument('-n', '--no-mirror', dest='mirror', action='store_false',
                        help='do not archive pastebin using the scrape API.')
    parser.add_argument('-k', '--api-key', dest='api_key', type=str, default=None, 
                        help='pastebin API key. only required with --trending option')
    parser.add_argument('-v', '--version', action='version', version='0.1.0')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', default=False,
                        help='suppresses printing of non-essential UI output, including paste ids and stats. '\
                        'default is false (show everything).')
    parser.set_defaults(mirror=True)
    args = parser.parse_args()

    if args.trending and args.api_key is None:
        parser.error('--api-key must be included with --trending option')

    if args.output_format == 'sqlite' and os.path.isdir(args.output):
        parser.error('--output must specify a file (not directory) when --output-format=sqlite')

    if not args.mirror and not args.trending:
        parser.error('at least one of --mirror or --trending must be included')

    args.rate = max(1, args.rate)

    return args

def archive_scrape_pastes(last_archive_time, scraper, storage, rate, quiet):
    if time.time() - last_archive_time >= rate:
        recent_pastes = [x for x in scraper.get_recent_pastes() \
                         if not storage.has_paste_content('paste_content', x['key'])]
        print('[*] Fetching {} new pastes'.format(len(recent_pastes)), file=sys.stderr)
        global session_pastes_count
        session_pastes_count += len(recent_pastes)
        for paste in recent_pastes:
            key = paste['key']
            storage.save_paste_reference('paste', key, paste['date'], paste['size'],
                                         paste['expire'], paste['title'], paste['syntax'],
                                         user=paste['user'])
            content = scraper.get_paste_content(key)
            if content is not None:
                storage.save_paste_content('paste_content', key, content)
                if not quiet:
                    print(key, file=sys.stdout)
            time.sleep(0.1) # waiting a 1/10th of a second seems to help download clogging 
        # probably dont want to flood the screen - how often should we display stats?
        # print('[*] Total pastes downloaded this session: {}'.format(session_pastes_count), file=sys.stdere)
        print('[*] Waiting {} seconds before next paste scrape'.format(rate), file=sys.stderr)
        return time.time()
    else: return last_archive_time

def archive_trending_pastes(last_archive_time, scraper, storage, quiet):
    # archive once per hour
    if time.time() - last_archive_time >= 60 * 60:
        trending_pastes = [x for x in scraper.get_trending_pastes() \
                           if not storage.has_paste_content('trending_paste_content', x['key'])]
        print('[*] Fetching {} new trending pastes'.format(len(trending_pastes)), file=sys.stderr)
        global session_trending_count
        session_trending_count += len(trending_pastes)
        for paste in trending_pastes:
            key = paste['key']
            storage.save_paste_reference('trending_paste', key, paste['date'], paste['size'],
                paste['expire'], paste['title'], paste['syntax'], hits=paste['hits'])
            content = scraper.get_paste_content(key)
            if content is not None:
                storage.save_paste_content('trending_paste_content', key, content)
                if not quiet:
                    print(key)
            time.sleep(0.1) # waiting a 1/10th of a second seems to help download clogging 
        print('[*] Trending pastes downloaded this session: {}'.format(session_trending_count), file=sys.stderr)
        print('[*] Waiting 1 hour before downloading new trending pastes', file=sys.stderr)
        return time.time()
    else: return last_archive_time

def main():
    print("\npastebin-mirror\n")

    args = parse_args()

    scraper = PastebinComScraper(args.api_key)
    if args.output_format == 'sqlite':
        storage = SQLite3Storage(location=args.output)
        try:
            storage.initialize_tables(args.trending)
        except sqlite3.OperationalError as e:
            print("[!] SQLite3 operational error when creating or accessing databasr file \"{}\": {}".format(args.output, e), file=sys.stderr)
            print("[!] Fatal error. Exiting...", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            storage = FlatFileStorage(location=args.output)
        except OSError as e:
            print("[!] Error creating or accessing flat file storage location: {}".format(e.strerror), file=sys.stderr)
            print("[!] Fatal error. Exiting...", file=sys.stderr)
            sys.exit(1)

    last_scrape = -args.rate
    last_trending = -60 * 60

    while True:
        if args.trending:
            last_trending = archive_trending_pastes(last_trending, scraper, storage, args.quiet)
        if args.mirror:
            last_scrape = archive_scrape_pastes(last_scrape, scraper, storage, args.rate, args.quiet)
        time.sleep(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("[!] Interrupted by user. Exiting...", file=sys.stderr)
        sys.exit(0)
