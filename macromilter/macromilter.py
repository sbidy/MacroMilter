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
## 3.5.2 - 04.01.2018 sbidy - update the tempfile handling for more security and some other fixes, re-introduce the UMASK
## 3.5.3 - 06.02.2018 sbidy - implementing the macro whitelisting, update the config parsing to json
## 3.6 - 03.01.2018 sbidy - fixing mutliple issues and bugs (#41, #38, #37, #35, #31, #30). Add MIME header for the different  stages.
## 3.6.1 - 25.09.2019 sbidy - update and fixing filehandle exception in tempfile. Added config function to dump the mail body to file (DUMP_BODY)

# The MIT License (MIT)

# Copyright (c) 2019 Stephan Traub - audius GmbH, www.audius.de

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
import olefile
import json

from sets import Set
from oletools import olevba, mraptor
from Milter.utils import parse_addr
from socket import AF_INET6
from ConfigParser import SafeConfigParser
from oletools.olevba import VBA_Parser


# use backport if needed
if sys.version_info[0] <= 2:
	from zipfile import ZipFile, is_zipfile
else:
	# Python 3.x+
	from zipfile import ZipFile, is_zipfile

## Config see ./config.ini
__version__ = '3.6.1'  # version

# get the config from FHS conform dir (bug #13)
CONFIG = os.path.join(os.path.dirname("/etc/macromilter/"),"config.ini")
if not os.path.isfile(CONFIG):
	CONFIG = os.path.join(os.path.dirname(__file__),"config.ini")

# get the configuration items
if os.path.isfile(CONFIG):
	config = SafeConfigParser()
	config.read(CONFIG)
	SOCKET = config.get('Milter', 'SOCKET')
	try:
		UMASK = int(config.get('Milter', 'UMASK'), base=0)
	except:
		UMASK = 0o0077
	TIMEOUT = config.getint('Milter', 'TIMEOUT')
	MAX_FILESIZE = config.getint('Milter', 'MAX_FILESIZE')
	MESSAGE = config.get('Milter', 'MESSAGE')
	MAX_ZIP = config.getint('Milter', 'MAX_ZIP')
	REJECT_MESSAGE = config.getboolean('Milter', 'REJECT_MESSAGE')
	LOGFILE_DIR = config.get('Logging', 'LOGFILE_DIR')
	LOGFILE_NAME = config.get('Logging', 'LOGFILE_NAME')
	LOGLEVEL = config.getint('Logging', 'LOGLEVEL')
	DUMP_BODY = config.getboolean('Milter', 'DUMP_BODY')
else:
	sys.exit("Please check the config file! Config path: %s" % CONFIG)
# =============================================================================

LOGFILE_PATH = os.path.join(LOGFILE_DIR, LOGFILE_NAME)
HASHTABLE_PATH = os.path.join(LOGFILE_DIR, "hashtable.db")

# Config check
if DUMP_BODY is None:
	DUMP_BODY = False

# fallback if a file can't detect by the file magic
EXTENSIONS = ".dot",".doc",".xls",".docm",".dotm",".xlsm",".xlsb",".pptm", ".ppsm", ".rtf", ".mht", ".ppt"

# Set up a specific logger with our desired output level
log = logging.getLogger('MacroMilter')
# disable logging by default - enable it in main app:
log.setLevel(logging.CRITICAL+1)

Hash_Whitelist = None
hashtable = None
WhiteList = None

# Custom exception class for archive bomb exception
class TooManyZipException(Exception):
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
		self.recipients = [] # list of recipients
		self.messageToParse = StringIO.StringIO()
		self.canon_from = '@'.join(parse_addr(mailfrom))
		self.messageToParse.write('From %s %s\n' % (self.canon_from, time.ctime()))
		return Milter.CONTINUE

	@Milter.noreply
	def envrcpt(self, to, *str):
		# remove the < and >
		self.recipients.append(to[1:-1])
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
			
			if self.sender_is_in_whitelist():
				self.addheader('X-MacroMilter-Status', 'Whitelisted')
				return Milter.ACCEPT
			else:
				return self.checkforVBA(msg)

		except Exception:
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			log.error("Unexpected error - fall back to ACCEPT: %s %s %s" % (exc_type, fname, exc_tb.tb_lineno))
			self.addheader('X-MacroMilter-Status', 'Unchecked')
			return Milter.CONTINUE

	## ==== Data processing ====

	def fileHasAlreadyBeenParsed(self, data):
		# generate Hash from file
		hash_data = hashlib.md5(data).hexdigest()
		# check if file is already parsed
		if hash_data in hashtable:
			log.warning("[%d] Attachment %s already parsed: REJECT" % (self.id, hash_data))
			return True
		else:
			# check if the attachment is a SHA
			hash_data = hashlib.sha256(data).hexdigest()
			if hash_data in hashtable:
				log.warning("[%d] Attachment %s already parsed: REJECT" % (self.id, hash_data))
				return True
			else:
				return False

	def addHashtoDB(self, data):
		hash_data = hashlib.sha256(data).hexdigest()
		hashtable.add(hash_data)
		with open(HASHTABLE_PATH, "a") as hashdb:
			hashdb.write(hash_data + '\n')

		log.debug("[%d] File added: %s" % (self.id, hash_data))

	def removeHashFromDB(self, data):
		hash_data = hashlib.sha256(data).hexdigest()
		hashtable.discard(hash_data)
		with open(HASHTABLE_PATH, "r+") as hashdb:
			for line in hashdb:
				if line != (hash_data + "\n"):
					hashdb.write(line)
		# legacy MD5
		hash_data = hashlib.md5(data).hexdigest()
		hashtable.discard(hash_data)		
		with open(HASHTABLE_PATH, "r+") as hashdb:
			for line in hashdb:
				if line != (hash_data + "\n"):
					hashdb.write(line)


	def checkforVBA(self, msg):
		'''
			Checks if it contains a vba macro and checks if user is whitelisted or file already parsed
		'''
		# Accept all messages with no attachment
		result = Milter.ACCEPT
		# check if the body must be replaced
		newbody = False
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

					if attachment is None and filename is None:
						return Milter.CONTINUE
					log.debug('[%d] Analyzing attachment: %r' % (self.id, filename))
					attachment_lowercase = attachment.lower()
					attachment_fileobj = StringIO.StringIO(attachment)

					# check if file was already parsed
					if self.fileHasAlreadyBeenParsed(attachment):
						if REJECT_MESSAGE is False:
							part.set_payload('This attachment has been removed because it contains a suspicious macro.')
							self.addheader('X-MacroMilter-Status', 'Suspicious macro')
							part.set_type('text/plain')
							part.replace_header('Content-Transfer-Encoding', '7bit')
							newbody = True
						else:
							if DUMP_BODY:
								self.writeBodyDump(msg)
							return Milter.REJECT

					# check if this is a supported file type (if not, just skip it)
					# TODO: this function should be provided by olevba
					elif olefile.isOleFile(attachment_fileobj) or is_zipfile(attachment_fileobj) or 'http://schemas.microsoft.com/office/word/2003/wordml' in attachment \
						or ('mime' in attachment_lowercase and 'version' in attachment_lowercase \
						and 'multipart' in attachment_lowercase):
						vba_code_all_modules = ''
						# check if the attachment is a zip
						if not olefile.isOleFile(attachment_fileobj):
							extn = (os.path.splitext(filename)[1]).lower()
							# skip non archives
							if is_zipfile(attachment_fileobj) and not (".docx" in extn or ".xlsx" in extn  or ".pptx" in extn):
								# extract all file in zip and add
								try:
									zipvba = self.getZipFiles(attachment, filename)
									vba_code_all_modules += zipvba + '\n'
								except TooManyZipException:
									log.warning("[%d] Attachment %s is reached the max. nested zip count! ZipBomb?: REJECT" % (self.id, filename))
									# rewrite the reject message 
									self.setreply('550', '5.7.2', "The message contains a suspicious archive and was rejected!")
									return Milter.REJECT

						# check the rest of the message
						try:
							vba_parser = olevba.VBA_Parser(filename='message', data=attachment)
							for (subfilename, stream_path, vba_filename, vba_code) in vba_parser.extract_all_macros():
								vba_code_all_modules += vba_code + '\n'
						except olevba.FileOpenError:
							log.error('[%d] Error while processing the message. Possible encrypted zip detected.' % self.id)
						
						# check the macro code whitelist
						if vba_code_all_modules is not None:
							if self.macro_is_in_whitelist(vba_code_all_modules):
								# macro code is in whitelist
								self.removeHashFromDB(attachment)
								self.addheader('X-MacroMilter-Status', 'Whitelisted')
								continue

						# run the mraptor
						m = mraptor.MacroRaptor(vba_code_all_modules)
						m.scan()
						# suspicious 
						if m.autoexec and (m.execute or m.write):
							# Add sha256 to the database
							self.addHashtoDB(attachment)
							# Replace the attachment or reject it
							if REJECT_MESSAGE:
								log.warning('[%d] The attachment %r contains a suspicious macro: REJECT' % (self.id, filename))
								self.addheader('X-MacroMilter-Status', 'Suspicious macro')
								result = Milter.REJECT
								if DUMP_BODY:
									self.writeBodyDump(msg)
							else:
								log.warning('[%d] The attachment %r contains a suspicious macro: replace it with a text file' % (self.id, filename))
								self.addheader('X-MacroMilter-Status', 'Suspicious macro')
								part.set_payload('This attachment has been removed because it contains a suspicious macro.')
								part.set_type('text/plain')
								part.replace_header('Content-Transfer-Encoding', '7bit')
								newbody = True
						else:
							log.debug('[%d] The attachment %r is clean.' % (self.id, filename))

		except Exception:
			log.error('[%d] Error while processing the message' % self.id)
			exc_type, exc_value, exc_traceback = sys.exc_info()
			lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
			exep = ''.join('!! ' + line for line in lines)
			log.debug("[%d] Exception code: [%s]" % (self.id, exep))
		
		if newbody:
			body = self.removeHader(msg)
			self.message = io.BytesIO(body)
			self.replacebody(body)
			log.info('[%d] Message relayed' % self.id)
			result = Milter.ACCEPT
		return result

	def removeHader(self, msg):
		'''
			Removes the header form the MIME mail to prevent a duplication. Retruns the raw body as string.
			The preamble for non-MIME clients is removed. Non-MIME clients can't read the attachement.
		'''
		# remove header from the body
		# ToDo: Get the boundary to determine the line beginning better
		body = str(msg)
		index = 0
		for lines in body.splitlines():
			# regarding the https://www.w3.org/Protocols/rfc1341/7_2_Multipart.html
			# in a multipart the first boundary beings with '--'
			if lines.startswith("--"):
				break
			else:
				index = index + 1
		return '\r\n'.join(body.splitlines()[index:])

	def getZipFiles(self, attachment, filename):
		'''
			Checks a zip for parseable files and extracts all macros
		'''
		log.debug("[%d] Found attachment with archive extension - file name: %s" % (self.id, filename))
		vba_code_all_modules = ''
		file_object = StringIO.StringIO(attachment)
		files_in_zip = self.zipwalk(file_object,0,[])
			
		for zip_name, zip_data in files_in_zip:
			# checks if it is a file
						
			zip_mem_data = StringIO.StringIO(zip_data)
			name, ext = os.path.splitext(zip_name.filename)
			# send to the VBA_Parser
			# fallback with extensions - maybe removed in future releases
			if olefile.isOleFile(zip_mem_data) or ext in EXTENSIONS:
				log.info("[%d] File in zip detected! Name: %s - check for VBA" % (self.id, zip_name.filename))
				vba_parser = olevba.VBA_Parser(filename=zip_name.filename, data=zip_data)
				for (subfilename, stream_path, vba_filename, vba_code) in vba_parser.extract_all_macros():
					vba_code_all_modules += vba_code + '\n'
		return vba_code_all_modules

	def sender_is_in_whitelist(self):
		'''
		Lookup if the sender is at the whitelist
		'''
		global WhiteList
		msg_from = self.canon_from
		msg_to = self.recipients

		# return if not RFC char detected
		if "\'" in msg_from:
			return False
		if "\'" in msg_to:
			return False

		if WhiteList is not None:
			log.debug("[%d] Whitelist compare: %s = %s" % (self.id, msg_from, msg_to))
			# check if it is a list
			for name in WhiteList:
				if name not in (None, ''):
					if any(name in s for s in msg_from):
						log.info("Whitelisted user %s - accept all attachments" % (msg_from))	
						return True
					if any(name in s for s in msg_to):
						log.info("Whitelisted user %s - accept all attachments" % (msg_to))
						return True
		return False

	def macro_is_in_whitelist(self, vbastring):
		'''
		Lookup for macro hash in whitelist
		'''
		global Hash_Whitelist
		# create hex over macro code
		vba_hex = vbastring.encode("hex")
		# generate sha256 hash
		vba_hash = hashlib.sha256(vba_hex).hexdigest()
		log.info("[%d] The macro hash is: %s" % (self.id, vba_hash))

		if Hash_Whitelist is not None:
			for hash in Hash_Whitelist:
				if hash in vba_hash:
					log.info("[%d] Whitelisted macro code %s - accept attachment" % (self.id, vba_hash))
					return True
		return False

	## === Support Functions ===
	'''
			Walks through the zip file and extracts all data for VBA scanning
			:return: File content generator
	'''
	def zipwalk(self, zfilename, count, tmpfiles):

		z = ZipFile(zfilename,'r')
		# start walk
		for info in z.infolist():
			# 35
			is_encrypted = info.flag_bits & 0x1 
			if not is_encrypted:
				fname = info.filename
				data = z.read(fname)
				extn = (os.path.splitext(fname)[1]).lower()

				# create a random secure temp file
				tmp_fs, tmpfpath = tempfile.mkstemp(suffix=extn)
				# add tmp filename to list
				tmpfiles.append(tmpfpath)
				
				if extn=='.zip' or extn=='.7z':
					checkz=False
					# use the file descriptor to write to the file
					tmpfile = os.fdopen(tmp_fs, "w")
					tmpfile.write(data)
					# Close the file to avoid the open file exception
					tmpfile.close()

					if is_zipfile(tmpfpath):
						checkz=True
						count = count+1
						# check each round
						if count > MAX_ZIP:
							self.deleteFileRecursive(tmpfiles)
							tmpfiles = []
							raise ToManyZipException("[%d] Too many nested zips found - possible zipbomb!" % self.id)
					if checkz and not olefile.isOleFile(data):
						try:
							# recursive call if nested
							for x in self.zipwalk(tmpfpath, count, tmpfiles):
								yield x
						except Exception:
							self.deleteFileRecursive(tmpfiles)
							tmpfiles = []
							raise 
				else:
					# close filehandler if not used
					os.close(tmp_fs)
					# return the generator
					yield (info, data)
		# cleanup tmp
		self.deleteFileRecursive(tmpfiles)
		tmpfiles = []

	'''
		Delete the files recursive from the tmp folder
	'''
	def deleteFileRecursive(self, filelist):
		for sfile in filelist:
			try:
				os.remove(sfile)
				log.debug("[%d] File %s removed from tmp folder" % (self.id, sfile))
			except OSError:
				pass

	'''
		Write the dump of the mail body to the logging folder
	'''
	def writeBodyDump(self, msg):
		try:
			dumpname = time.strftime("%Y%m%d-%H%M%S")
			dumpname = "Dump_"+dumpname+"_"+str(self.id)
			dumpfile = os.path.join(LOGFILE_DIR, dumpname)
			with open(dumpfile, 'w') as f:
				f.write(str(msg))
			f.close()
			log.info("Body dump written in %s" % dumpfile)
		except Exception:
				log.error("Cant write body dump")

## ===== END CLASS ========

## ==== start MAIN ========

def WhiteListLoad():
	'''
		Function to load the data from the WhiteList file and load into memory
	'''
	global WhiteList, Hash_Whitelist
	WhiteList = json.loads(config.get("Whitelist", "Recipients"))
	Hash_Whitelist = json.loads(config.get("Whitelist", "Macrohash"))

def HashTableLoad():
	'''
		Load the hash info from file to memory
	'''
	# Load hashes from file
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
	# rotation handled by logrotatd
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

	# ensure desired permissions on unix socket
	os.umask(UMASK)

	# set the "last" fall back to ACCEPT if exception occur
	Milter.set_exception_policy(Milter.ACCEPT)

	# start the milter
	Milter.runmilter("MacroMilter", SOCKET, TIMEOUT)

	print("%s MacroMilter shutdown" % time.strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == "__main__":
	main()
