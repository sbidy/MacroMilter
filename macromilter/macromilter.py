#!/usr/bin/env python
## Macro Milter for postfix - https://github.com/sbidy/MacroMilter
##
## 1.4 - 15.12.2015 sbidy - Update comments, add hash-set for lookup and safe to persistent
## 1.5 - 16.12.2015 sbidy - Add date-time to performance log
## 1.6 - 16.12.2015 sbidy - Change to TCP Socket, Socket an timeout to global, update name to "MacroMilter", set_exception_policy to ACCEPT, fix timer bug for performance data
## 1.7 - 05.01.2016 sbidy - Adding Extensionlogging
## 1.8 - 07.01.2016 sbidy - Commit at github, add the privacy statement
## 1.9 - 12.01.2016 sbidy - Clean up the code - deleted the virus total function. Hive off to a separate project/milter
## 2.0 - 12.01.2016 sbidy - Add spam header "X-Spam-Flag" to yes for a non-MIME Message
## 2.1 - 15.02.2016 sbidy - Fix multi attachment bug, now parses multiple attachments, docm and xlsm added
## 2.2 - 18.02.2016 sbidy - Fix while loop bug
## 2.3 - 22.02.2016 sbidy - Fix multiple entry at hashtable and remove ppt
## 2.4 - 07.03.2016 sbidy - Update bad zip file exception and disable file logging + x-spam-flag
## 2.5 - 07.03.2016 sbidy - Fix run.log bug and disable connect log
## 2.6 - 08.03.2016 Gulaschcowboy - Added CFG_DIR, fixed some paths, added systemd.service, Readme.opensuse and logrotate script
## 2.7 - 18.03.2016 sbidy - Added rtf to file list
## 2.8 - 29.03.2016 sbidy - Added some major fixes and code cleanup, added the zip extraction for .zip files regarding issue #5
## 2.8.1 - 30.03.2016 sbidy - Fix the str-exception, added some logging informations
## 2.9 - 20.05.2016 sbidy - Fix issue #6 - queue not empty after log file can't written, write extension data to file deleted
## 2.9.1 - 20.05.2016 sbidy - Additional fixes for #6
## 2.9.2 - 27.06.2016 sbidy - Add changes from heinrichheine and merge to master
## 2.9.3 - 27.06.2016 heinrichheine/sbidy - Tested and updated version, some fixes added
# -------------------------- V3 -----------------------------------------
## 3.0 - 05.01.2017 sbidy - Add some enhancements and major changes, used mraptor from oletools, cleanup and remove the multi-thread feature, add configuration file
## 3.1 - 10.01.2017 sbidy - Bugfix for whitelist exception
## 3.2 - 12.01.2017 sbidy - Fix for exceptions.UnboundLocalError, possible fix for #10 zip - extraction did not work properly
## 3.3 - 05.10.2017 sbidy - Update directory for FHS conformity see #13
## 3.4 - 27.10.2017 sbidy - Update and fix some bugs #19, #18 and #17 - create release 
## 3.5.1 - 03.01.2018 sbidy - Fix for #31 #27 #29, some updates for the logging and umask

# The MIT License (MIT)

# Copyright (c) 2016 Stephan Traub - audius GmbH, www.audius.de

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import Milter
import StringIO
import time
import email
import sys
import re
import hashlib
import os
import errno
import logging
import logging.handlers
import io
import traceback
import tempfile
import shutil

from sets import Set
from oletools import olevba, mraptor
from Milter.utils import parse_addr
from socket import AF_INET6
from ConfigParser import SafeConfigParser

# use backport if needed
if sys.version_info[0] <= 2:
	# Python 2.x
	if sys.version_info[1] <= 6:
		# Python 2.6
		# use is_zipfile backported from Python 2.7:
		from oletools.thirdparty.zipfile27 import ZipFile, is_zipfile
	else:
		# Python 2.7
		from zipfile import ZipFile, is_zipfile
else:
	# Python 3.x+
	from zipfile import ZipFile, is_zipfile

## Config see ./config.ini
__version__ = '3.5.1'  # version

# get the config from FHS conform dir (bug #13)
CONFIG = os.path.join(os.path.dirname("/etc/macromilter/"),"config.ini")
if not os.path.isfile(CONFIG):
	CONFIG = os.path.join(os.path.dirname(__file__),"config.ini")

# get the configuration items
if os.path.isfile(CONFIG):
	config = SafeConfigParser()
	config.read(CONFIG)
	SOCKET = config.get('Milter', 'SOCKET')
	#UMASK = int(config.get('Milter', 'UMASK'), base=0)
	TIMEOUT = config.getint('Milter', 'TIMEOUT')
	MAX_FILESIZE = config.getint('Milter', 'MAX_FILESIZE')
	MESSAGE = config.get('Milter', 'MESSAGE')
	MAX_ZIP = config.getint('Milter', 'MAX_ZIP')
	REJECT_MESSAGE = config.getboolean('Milter', 'REJECT_MESSAGE')
	LOGFILE_DIR = config.get('Logging', 'LOGFILE_DIR')
	LOGFILE_NAME = config.get('Logging', 'LOGFILE_NAME')
	LOGLEVEL = config.getint('Logging', 'LOGLEVEL')
else:
	sys.exit("Please check the config file! Config path: %s" % CONFIG)
# =============================================================================

LOGFILE_PATH = os.path.join(LOGFILE_DIR, LOGFILE_NAME)
HASHTABLE_PATH = os.path.join(LOGFILE_DIR, "hashtable.db")

EXTENSIONS = ".dot",".doc",".xls",".docm",".dotm",".xlsm",".xlsb",".pptm", ".ppsm"

# Set up a specific logger with our desired output level
log = logging.getLogger('MacroMilter')
# disable logging by default - enable it in main app:
log.setLevel(logging.CRITICAL+1)

hash_to_write = None
hashtable = None
WhiteList = None

# Custom exception class for archive bomb exception
class ToManyZipException(Exception):
	pass

## Customized milter class - partly copied from
## https://github.com/jmehnle/pymilter/blob/master/milter-template.py
class MacroMilter(Milter.Base):
	'''Base class for MacroMilter to move boilerplate connection stuff away from the real
		business logic for macro parsing
	'''
	def __init__(self):  # A new instance with each new connection.
		self.id = Milter.uniqueID()  # Integer incremented with each call.
		self.messageToParse = None
		self.level = 0
		self.headercount = 0
		self.size = 0

	@Milter.noreply
	def connect(self, IPname, family, hostaddr):

		# define all vars
		self.IP = hostaddr[0]
		self.port = hostaddr[1]
		if family == AF_INET6:
			self.flow = hostaddr[2]
			self.scope = hostaddr[3]
		else:
			self.flow = None
			self.scope = None
		self.IPname = IPname  # Name from a reverse IP lookup
		self.messageToParse = None  # content
		log.debug("[%d] Connect from %s at %s" % (self.id, IPname, hostaddr)) # for logging
		return Milter.CONTINUE

	@Milter.noreply
	def envfrom(self, mailfrom, *str):
		self.messageToParse = StringIO.StringIO()
		self.canon_from = '@'.join(parse_addr(mailfrom))
		self.messageToParse.write('From %s %s\n' % (self.canon_from, time.ctime()))
		return Milter.CONTINUE

	@Milter.noreply
	def envrcpt(self, to, *str):
		return Milter.CONTINUE

	@Milter.noreply
	def header(self, header_field, header_field_value):
		self.messageToParse.write("%s: %s\n" % (header_field, header_field_value))
		return Milter.CONTINUE

	@Milter.noreply
	def eoh(self):
		self.messageToParse.write("\n")
		return Milter.CONTINUE

	@Milter.noreply
	def body(self, chunk):
		self.messageToParse.write(chunk)
		return Milter.CONTINUE

	def close(self):
		# stop timer at close
		return Milter.CONTINUE

	def abort(self):
		# nothing to clean up
		return Milter.CONTINUE

	def eom(self):
		'''This method is called when the end of the email message has been reached.
		   This event also triggers the milter specific actions
		'''
		try:
			# set data pointer back to 0
			self.messageToParse.seek(0)
			# use email from package email to parse the message string
			msg = email.message_from_string(self.messageToParse.getvalue())
			# Set Reject Message - definition from here
			# https://www.iana.org/assignments/smtp-enhanced-status-codes/smtp-enhanced-status-codes.xhtml
			self.setreply('550', '5.7.1', MESSAGE)
			
			if self.sender_is_in_whitelist(msg):
				return Milter.ACCEPT
			else:
				return self.checkforVBA(msg)

		except Exception:
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			log.error("Unexpected error - fall back to ACCEPT: %s %s %s" % (exc_type, fname, exc_tb.tb_lineno))
			return Milter.ACCEPT

	## ==== Data processing ====

	def fileHasAlreadyBeenParsed(self, data):
		# generate Hash from file
		hash_data = hashlib.md5(data).hexdigest()
		# check if file is already parsed
		if hash_data in hashtable:
			log.warning("[%d] Attachment %s already parsed: REJECT" % (self.id, hash_data))
			return True
		else:
			return False

	def addHashtoDB(self, data):
		hash_data = hashlib.md5(data).hexdigest()
		hashtable.add(hash_data)
		with open(HASHTABLE_PATH, "a") as hashdb:
			hashdb.write(hash_data + '\n')

		log.debug("[%d] File added: %s" % (self.id, hash_data))

	def checkforVBA(self, msg):
		'''
			Checks if it contains a vba macro and checks if user is whitelisted or file already parsed
		'''
		# Accept all messages with no attachment
		result = Milter.ACCEPT
		try:
			for part in msg.walk():
				# for name, value in part.items():
				#     log.debug(' - %s: %r' % (name, value))
				content_type = part.get_content_type()
				log.debug('[%d] Content-Type: %r' % (self.id, content_type))
				# TODO: handle any content-type, but check the file magic?
				if not content_type.startswith('multipart'):
					filename = part.get_filename(None)
					attachment = part.get_payload(decode=True)
					if attachment is None:
						return Milter.CONTINUE
					log.debug('[%d] Analyzing attachment: %r' % (self.id, filename))
					attachment_lowercase = attachment.lower()
					# check if file was already parsed
					if self.fileHasAlreadyBeenParsed(attachment):
						return Milter.REJECT
					# check if this is a supported file type (if not, just skip it)
					# TODO: this function should be provided by olevba
					if attachment.startswith(olevba.olefile.MAGIC) or is_zipfile(StringIO.StringIO(attachment)) or 'http://schemas.microsoft.com/office/word/2003/wordml' in attachment \
						or ('mime' in attachment_lowercase and 'version' in attachment_lowercase \
						and 'multipart' in attachment_lowercase):
						vba_code_all_modules = ''
						# check if the attachment is a zip
						if is_zipfile(StringIO.StringIO(attachment)) and not attachment.startswith(olevba.olefile.MAGIC):
							# extract all file in zip and add
							try:
								zipvba = self.getZipFiles(attachment, filename)
								vba_code_all_modules += zipvba + '\n'
							except ToManyZipException:
								log.warning("[%d] Attachment %s is reached the max. nested zip count! ZipBomb?: REJECT" % (self.id, filename))
								# rewrite the reject message 
								self.setreply('550', '5.7.2', "The message contains a suspicious archive and was rejected!")
								return Milter.REJECT
						# check the rest of the message
						vba_parser = olevba.VBA_Parser(filename='message', data=attachment)
						for (subfilename, stream_path, vba_filename, vba_code) in vba_parser.extract_all_macros():
							vba_code_all_modules += vba_code + '\n'
						# run the mraptor
						m = mraptor.MacroRaptor(vba_code_all_modules)
						m.scan()
						if m.suspicious:
							# Add MD5 to the database
							self.addHashtoDB(attachment)
							# Replace the attachment or reject it
							if REJECT_MESSAGE:
								log.warning('[%d] The attachment %r contains a suspicious macro: REJECT' % (self.id, filename))
								result = Milter.REJECT
							else:
								log.warning('[%d] The attachment %r contains a suspicious macro: replace it with a text file' % (self.id, filename))
								part.set_payload('This attachment has been removed because it contains a suspicious macro.')
								part.set_type('text/plain')
								part.replace_header('Content-Transfer-Encoding', '7bit')
						else:
							log.debug('[%d] The attachment %r is clean.' % (self.id, filename))

		except Exception:
			log.error('[%d] Error while processing the message' % self.id)
			exc_type, exc_value, exc_traceback = sys.exc_info()
			lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
			exep = ''.join('!! ' + line for line in lines)
			log.debug("[%d] Exeption code: [%s]" % (self.id, exep))

		if REJECT_MESSAGE is False:
			body = str(msg)
			self.message = io.BytesIO(body)
			self.replacebody(body)
			log.info('[%d] Message relayed' % self.id)
		return result

	def getZipFiles(self, attachment, filename):
		'''
			Checks a zip for parsable files and extracts all macros
		'''
		log.debug("[%d] Found attachment with archive extension - file name: %s" % (self.id, filename))
		vba_code_all_modules = ''
		file_object = StringIO.StringIO(attachment)
		files_in_zip = self.zipwalk(file_object,0,[])
			
		for zip_name, zip_data in files_in_zip:
			# checks if it is a file
			log.info("[%d] File in zip detected! Name: %s - check for VBA" % (self.id, zip_name.filename))
			
			zip_mem_data = StringIO.StringIO(zip_data)
			name, ext = os.path.splitext(zip_name.filename)
			# send to the VBA_Parser
			if zip_mem_data.getvalue().startswith(olevba.olefile.MAGIC) or ext in EXTENSIONS:
				vba_parser = olevba.VBA_Parser(filename=zip_name.filename, data=zip_data)
				for (subfilename, stream_path, vba_filename, vba_code) in vba_parser.extract_all_macros():
					vba_code_all_modules += vba_code + '\n'
		return vba_code_all_modules

	def sender_is_in_whitelist(self, msg):
		'''
			Lookup if the sender is at the whitelist - @domains.com must be supported
		'''
		global WhiteList
		sender = ''
		msg_from = msg['From']
		if msg_from is not None:
			sender = str(re.findall('<([^"]*)>', msg_from ))

		if WhiteList is not None:
			for name in WhiteList:
				if re.search(name, sender) and not name.startswith("#"):
					log.info("Whitelisted user %s - accept all attachments" % (msg_from))
					return True
		return False

	## === Support Functions ===
	'''
			Walks through the zip file and extracts all data for VBA scanning
			:return: File content generator
	'''
	def zipwalk(self, zfilename, count, tmpfiles):
		# TODO: Maybe better in memory?!
		tempdir = tempfile.gettempdir()
		z = ZipFile(zfilename,'r')
		# start walk
		for info in z.infolist():
			fname = info.filename
			data = z.read(fname)
			extn = (os.path.splitext(fname)[1]).lower()

			if extn=='.zip':
				checkz=False
				tmpfpath = os.path.join(tempdir,os.path.basename(fname))
				oldumask = os.umask(0o0066)
				open(tmpfpath,'w+b').write(data)
				os.umask(oldumask)
				# add tmp filename to list
				tmpfiles.append(tmpfpath)
				if is_zipfile(tmpfpath):
					checkz=True
					count = count+1
					# check each round
					if count > MAX_ZIP:
						self.deleteFileRecursive(tmpfiles)
						raise ToManyZipException("[%d] Too many nested zips found - possible zipbomb!" % self.id)
				if checkz and not data.startswith(olevba.olefile.MAGIC):
					try:
						# recursive call if nested
						for x in self.zipwalk(tmpfpath, count, tmpfiles):
							yield x
					except Exception:
						raise 
				try:
					# remove the files from tmp
					self.deleteFileRecursive(tmpfiles)
				except:
					pass
			else:
				# retrun the generator
				yield (info, data)

	def deleteFileRecursive(self, filelist):
		for sfile in filelist:
			os.remove(sfile)
			log.debug("[%d] File %s removed from tmp folder" % (self.id, sfile))
## ===== END CLASS ========

## ==== start MAIN ========

def WhiteListLoad():
	'''
		Function to load the data from the WhiteList file and load into memory
	'''
	global WhiteList
	WhiteList = config.get("Whitelist", "Recipients")

def HashTableLoad():
	'''
		Load the hash info from file to memory
	'''
	# Load Hashs from file
	global hashtable
	oldumask = os.umask(0o0026)
	hashtable = set(line.strip() for line in open(HASHTABLE_PATH, 'a+'))
	os.umask(oldumask)

def main():
	
	# make sure the log directory exists:
	try:
		os.makedirs(LOGFILE_DIR,0o0027)
	except:
		pass

	# Load the whitelist into memory
	WhiteListLoad()
	HashTableLoad()
	# Add the log message handler to the logger
	# rotation handeld by logrotatd
	oldumask = os.umask(0o0026)
	handler = logging.handlers.WatchedFileHandler(LOGFILE_PATH, encoding='utf8')
	# create formatter and add it to the handlers
	formatter = logging.Formatter('%(asctime)s - %(levelname)8s: %(message)s')
	handler.setFormatter(formatter)
	log.addHandler(handler)
	os.umask(oldumask)

	# Loglevels are: 1 = Debug, 2 = Info, 3 = Error

	if LOGLEVEL == 2:
		log.setLevel(logging.INFO)
	elif LOGLEVEL == 3:
		log.setLevel(logging.WARNING)
	else:
		log.setLevel(logging.DEBUG)

	# Register to have the Milter factory create instances of the class:
	Milter.factory = MacroMilter
	flags = Milter.CHGBODY + Milter.CHGHDRS + Milter.ADDHDRS
	flags += Milter.ADDRCPT
	flags += Milter.DELRCPT
	Milter.set_flags(flags)  # tell Sendmail which features we use

	# start milter processing
	print("%s MacroMilter startup - Version %s" % (time.strftime('%Y-%m-%d %H:%M:%S'), __version__ ))
	print('logging to file %s' % LOGFILE_PATH)

	log.info('Starting MarcoMilter v%s - listening on %s' % (__version__, SOCKET))
	log.debug('Python version: %s' % sys.version)
	sys.stdout.flush()

	# set the "last" fall back to ACCEPT if exception occur
	Milter.set_exception_policy(Milter.ACCEPT)

	# start the milter
	Milter.runmilter("MacroMilter", SOCKET, TIMEOUT)

	print("%s MacroMilter shutdown" % time.strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == "__main__":
	main()
