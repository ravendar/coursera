#!/usr/bin/env python
"""
For downloading videos for Coursera classes. Given a class name and related cookie file, it scrapes the course listing page to get the week and class names, and then downloads the related videos into appropriately named files and directories.

Tested on Python 2.6.5.

Dependencies:
- BeautifulSoup 3
- argparser         # sudo easy_install argparse

Other:
- must point script at your browser's cookie file for authentication
  to coursera.org
  - Chrome users use "cookie.txt export" extension
- wget can optionally be used

If it's finding 0 sections, you probably have a bad cookies file.
Use -l listing.html and then examine that file -- if it's the non-logged-in
page then this is definitely your problem.

Examples:
coursera_dl.py -c cookies.txt -l listing.html -o saas --skip-download
"""

import sys, os, re, string
import urllib2, cookielib 
import tempfile
import subprocess
import argparse
from collections import namedtuple
from BeautifulSoup import BeautifulSoup        

def get_syllabus_url(className):
  """Return the Coursera index/syllabus URL."""
  return "http://class.coursera.org/%s/lecture/index" % className

def load_cookies_file(cookies_file):
  """Loads the cookies file. I am pre-pending the file with the special
  Netscape header because the cookie loader is being very particular about 
  this string."""
  NETSCAPE_HEADER = "# Netscape HTTP Cookie File"
  cookies = tempfile.NamedTemporaryFile()
  cookies.write(NETSCAPE_HEADER)
  cookies.write(open(cookies_file, 'r').read())
  cookies.flush()
  return cookies

def get_opener(cookies_file):
  """  """
  cj = cookielib.MozillaCookieJar()
  cookies = load_cookies_file(cookies_file)
  cj.load(cookies.name)
  return urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

def get_page(url, cookies_file):
  """Download an HTML page using the cookiejar."""
  opener = get_opener(cookies_file)
  return opener.open(url).read()

def get_syllabus(class_name, cookies_file, local_page=False):
  """ Get the course listing webpage."""
  if (not (local_page and os.path.exists(local_page))):
    url = get_syllabus_url(class_name)
    page = get_page(url, cookies_file)
    print "Downloaded %s (%d bytes)" % (url, len(page))
    # cache the page if we're in 'local' mode
    if (local_page):
      open(local_page, 'w').write(page)
  else:
    page = open(local_page).read()
  return page

def clean_filename(s):
  """Sanitize a string to be used as a filename."""
  # strip paren portions which contain trailing time length (...)
  s = re.sub("\([^\(]*$", "", s)
  s = s.strip().replace(':','-').replace(' ', '_')
  valid_chars = "-_.()%s%s" % (string.ascii_letters, string.digits)
  return ''.join(c for c in s if c in valid_chars)

def parse_syllabus(page):
  """Parses a Coursera course listing/syllabus page. 
  Each section is a week of classes."""
  Section = namedtuple('Section', 'name videos')
  Video = namedtuple('Video', 'name url')
  sections = []
  soup = BeautifulSoup(page)
  # traverse sections
  for stag in soup.findAll(attrs={'class':'list_header'}):
    assert stag.string != None, "couldn't find section"
    section_name = clean_filename(stag.string)
    print section_name
    videos = []
    # traverse videos
    for vtag in stag.parent.nextSibling.findAll('li'):
      assert vtag.a.contents[0], "couldn't get video name"
      vname = clean_filename(vtag.a.contents[0])
      print "  ", vname,
      # find the anchor with .mp4 reference
      url = vtag.find('a', {"href":re.compile("\.mp4")})["href"]
      print "  ", url
      videos.append(Video(vname, url))
    sections.append(Section(section_name, videos))
  print "Found %d sections and %d videos on this page" % \
    (len(sections), sum((len(s.videos) for s in sections)))
  if (not len(sections)):
    print "Probably bad cookies file (or wrong class name)"
  return sections

def download_videos(wget_bin, cookies_file, class_name, sections, overwrite=False, skip_download=False, only_section_num=None):
  """Downloads videos described by sections."""

  def format_section(num, section):
    return "%s_%02d_%s" % (class_name.upper(), num, section)

  def format_video(num, video):
    return "%02d_%s.mp4" % (num, video)

  for (secnum, (section, videos)) in enumerate(sections, 1):
    if only_section_num and secnum != only_section_num:
      continue
    sec = format_section(secnum, section)
    if not os.path.exists(sec):
      os.mkdir(sec)
    for (vidnum, (vname, url)) in enumerate(videos, 1):
      vidfn = os.path.join(sec, format_video(vidnum, vname))
      if overwrite or not os.path.exists(vidfn):
        if not skip_download: 
          download_file(url, vidfn, cookies_file, wget_bin)
        else: 
          open(vidfn, 'w').close()  # touch

def download_file(url, fn, cookies_file, wget_bin):
  """Downloads file and removes current file if aborted by user."""
  try:
    if wget_bin:
      download_file_wget(wget_bin, url, fn, cookies_file)
    else:
      download_file_nowget(url, fn, cookies_file)
  except KeyboardInterrupt as e: 
    print "\nKeyboard Interrupt -- Removing partial file:", fn
    os.remove(fn)
    sys.exit()

def download_file_wget(wget_bin, url, fn, cookies_file):
  """Downloads a file using wget.  Could possibly use python to stream files to
  disk, but wget is robust and gives nice visual feedback."""
  cmd = [wget_bin, url, "-O", fn, "--load-cookies", cookies_file]
  print "Executing wget:", cmd 
  retcode = subprocess.call(cmd)

def download_file_nowget(url, fn, cookies_file):
  """'Native' python downloader -- slower than wget."""
  print "Downloading %s -> %s" % (url, fn)
  urlfile = get_opener(cookies_file).open(url)
  chunk_sz = 1048576
  bytesread = 0
  f = open(fn, "w")
  while True:
    data = urlfile.read(chunk_sz)
    if not data:
      print "."
      break
    f.write(data)
    bytesread += len(data)
    print "\r%d bytes read" % bytesread,
    sys.stdout.flush()

def parseArgs():
  parser = argparse.ArgumentParser(description='Download Coursera.org videos.')
  # positional
  parser.add_argument('class_name', action='store', 
    help='name of the class (e.g. "nlp")')
  # required
  parser.add_argument('-c', '--cookies_file', dest='cookies_file', 
    action='store', required=True, help='full path to the cookies.txt file')
  # optional
  parser.add_argument('-w', '--wget_bin', dest='wget_bin', 
    action='store', default=None, help='wget binary if it should be used for downloading')
  parser.add_argument('-s', '--section_num', dest='only_section_num', type=int,
    action='store', help='only download this section number')
  parser.add_argument('-o', '--overwrite', dest='overwrite', 
    action='store_true', default=False, 
    help='whether existing video files should be overwritten (default: False)')
  parser.add_argument('-l', '--process_local_page', dest='local_page', 
    help='for debugging: uses or creates local cached version of syllabus page')
  parser.add_argument('--skip-download', dest='skip_download', 
    action='store_true', default=False, 
    help='for debugging: skip actual downloading of videos')
  args = parser.parse_args()
  # check arguments
  if not os.path.exists(args.cookies_file):
    raise IOError("Cookies file not found: " + args.cookies_file)
  return args

def main():
  args = parseArgs()
  page = get_syllabus(args.class_name, args.cookies_file, args.local_page)
  sections = parse_syllabus(page)
  download_videos(args.wget_bin, args.cookies_file, args.class_name, sections, args.overwrite, args.skip_download, args.only_section_num)

if __name__ == "__main__":
  main()