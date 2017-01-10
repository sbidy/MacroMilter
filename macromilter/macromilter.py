## Macro Milter for postfix - https://github.com/sbidy/MacroMilter
##
## 1.4 - 15.12.2015 sbidy - Update comments, add hash-set for lookup and safe to persistent
## 1.5 - 16.12.2015 sbidy - Add date-time to performance log
## 1.6 - 16.12.2015 sbidy - Change to TCP Socket, Socket an timeout to global, update name to "MacroMilter", set_exception_policy to ACCEPT, fix timer bug for performance data
## 1.7 - 05.01.2016 sbidy - Adding Extensionlogging
## 1.8 - 07.01.2016 sbidy - Commit at github, add the privacy statement
## 1.9 - 12.01.2016 sbidy - Clean up the code - deleted the virus total function. Hive off to a separate project/milter
## 2.0 - 12.01.2016 sbidy - Add spam header "X-Spam-Flag" to yes for a non-MIME Message
## 2.1 - 15.02.2016 sbidy - Fix multi attachment bug, now parses multible attachments, docm and xlsm added
## 2.2 - 18.02.2016 sbidy - Fix while loop bug
## 2.3 - 22.02.2016 sbidy - Fix multible entry at hashtable and remove ppt
## 2.4 - 07.03.2016 sbidy - Update bad zip file exception and disable file logging + x-spam-flag
## 2.5 - 07.03.2016 sbidy - Fix run.log bug and disable connect log
## 2.6 - 08.03.2016 Gulaschcowboy - Added CFG_DIR, fixed some paths, added systemd.service, Readme.opensuse and logrotate script
## 2.7 - 18.03.2016 sbidy - Added rtf to file list
## 2.8 - 29.03.2016 sbidy - Added some major fixes and code cleanup, added the zip extraction for .zip files regrading issue #5
## 2.8.1 - 30.03.2016 sbidy - Fix the str-exception, added some logging informations
## 2.9 - 20.05.2016 sbidy - Fix issue #6 - queue not empty after log fiel cant written, write extension data to file deleted
## 2.9.1 - 20.05.2016 sbidy - Additional fixes for #6
## 2.9.2 - 27.06.2016 sbidy - Add changes from heinrichheine and merge to master
## 2.9.3 - 27.06.2016 heinrichheine/sbidy - Tested and updated version, some fixes added
# -------------------------- V3 -----------------------------------------
## 3.0 - 05.01.2017 sbidy - Add some enhancements and major changes, used mraptor from oletools, cleanup and remove the multi-thread feature, add configuration file
## 3.1 - 10.01.2017 sbidy - Bugfix for whitelist expetion

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

from sets import Set
from oletools import olevba, mraptor
from Milter.utils import parse_addr
from socket import AF_INET6
from ConfigParser import SafeConfigParser

if True:
	from multiprocessing import Process as Thread, Queue
else:
	from threading import Thread
	from Queue import Queue
from Queue import Empty

# use backport if needed
if sys.version_info[0] <= 2:
	# Python 2.x
	if sys.version_info[1] <= 6:
		# Python 2.6
		# use is_zipfile backported from Python 2.7:
		from oletools.thirdparty.zipfile27 import is_zipfile
	else:
		# Python 2.7
		from zipfile import is_zipfile
else:
	# Python 3.x+
	from zipfile import is_zipfile

## Config see ./config.ini
__version__ = '3.0'  # version
CONFIG = os.path.join(os.path.dirname(__file__),"config.ini")

if os.path.isfile(CONFIG):
	config = SafeConfigParser()
	config.read(CONFIG)
	SOCKET = config.get('Milter', 'SOCKET')
	TIMEOUT = config.getint('Milter', 'TIMEOUT')
	MAX_FILESIZE = config.getint('Milter', 'MAX_FILESIZE')
	CFG_DIR = config.get('Milter', 'CFG_DIR')
	MESSAGE = config.get('Milter', 'MESSAGE')
	REJECT_MESSAGE = config.getboolean('Milter', 'REJECT_MESSAGE')
	LOGFILE_DIR = config.get('Logging', 'LOGFILE_DIR')
	LOGFILE_NAME = config.get('Logging', 'LOGFILE_NAME')
	LOGLEVEL = config.getint('Logging', 'LOGLEVEL')
else:
	sys.exit("Please check the config file! Config path: %s" % CONFIG)
# =============================================================================

LOGFILE_PATH = os.path.join(LOGFILE_DIR, LOGFILE_NAME)
HASHTABLE_PATH = os.path.join(LOGFILE_DIR, "hashtable.db")

# Set up a specific logger with our desired output level
log = logging.getLogger('MacroMilter')
# disable logging by default - enable it in main app:
log.setLevel(logging.CRITICAL+1)

hash_to_write = None
hashtable = None
WhiteList = None

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
		log.debug("connect from %s at %s" % (IPname, hostaddr)) # for logging
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
			log.warning("Attachment %s already parsed ! REJECT" % hash_data)
			return True
		else:
			return False

	def addHashtoDB(self, data):
		hash_data = hashlib.md5(data).hexdigest()
		hashtable.add(hash_data)
		with open(HASHTABLE_PATH, "a") as hashdb:
			hashdb.write(hash_data + '\n')

		log.debug("File Added %s" % hash_data)

	def checkforVBA(self, msg):
		'''
			Checks if it contains a vba macro and checks if user is whitelisted or file already parsed
		'''
		try:
			for part in msg.walk():
				# for name, value in part.items():
				#     log.debug(' - %s: %r' % (name, value))
				content_type = part.get_content_type()
				log.debug('[%d] Content-type: %r' % (self.id, content_type))
				# TODO: handle any content-type, but check the file magic?
				if not content_type.startswith('multipart'):
					filename = part.get_filename(None)
					log.debug('[%d] Analyzing attachment %r' % (self.id, filename))
					attachment = part.get_payload(decode=True)
					attachment_lowercase = attachment.lower()
					# chech if file alrady parsed
					if self.fileHasAlreadyBeenParsed(attachment):
						return Milter.REJECT
					# check if this is a supported file type (if not, just skip it)
					# TODO: this function should be provided by olevba
					if attachment.startswith(olevba.olefile.MAGIC) or is_zipfile(StringIO.StringIO(attachment)) or 'http://schemas.microsoft.com/office/word/2003/wordml' in attachment \
						or ('mime' in attachment_lowercase and 'version' in attachment_lowercase \
						and 'multipart' in attachment_lowercase):
						
						vba_parser = olevba.VBA_Parser(filename='message', data=attachment)
						vba_code_all_modules = ''
						for (subfilename, stream_path, vba_filename, vba_code) in vba_parser.extract_all_macros():
							vba_code_all_modules += vba_code + '\n'
						m = mraptor.MacroRaptor(vba_code_all_modules)
						m.scan()
						if m.suspicious:
							# Add MD5 to the database
							self.addHashtoDB(attachment)
							# Replace the attachment or reject it
							if REJECT_MESSAGE:
								log.warning('[%d] The attachment %r contains a suspicious macro. REJECT' % (self.id, filename))
								result = Milter.REJECT
							else :
								log.warning('[%d] The attachment %r contains a suspicious macro: replace it with a text file' % (self.id, filename))
								part.set_payload('This attachment has been removed because it contains a suspicious macro.')
								part.set_type('text/plain')
								part.replace_header('Content-Transfer-Encoding', '7bit')
								result = Milter.ACCEPT								
						else:
							log.debug('The attachment %r is clean.' % filename)
							result = Milter.ACCEPT

		except Exception:
			log.error('[%d] Error while processing the message' % self.id)
			result = Milter.ACCEPT

		if REJECT_MESSAGE is False:
			body = str(msg)
			self.message = io.BytesIO(body)
			self.replacebody(body)
			log.info('[%d] Message relayed' % self.id)
		return result

	def checkZIPforVBA(self, data, filename, msg): # NOT USED
		'''
			Checks a zip for parsesable files and send to the parser
		'''
		log.debug("Find Attachment with archive extension - File name: %s" % (filename))

		file_object = StringIO.StringIO(data)
		# self.size = len(StringIO(data))
		# print "Size:"+self.size
		files_in_zip = self.extract_zip(file_object)
		for zip_name, zip_data in files_in_zip.items():
			# checks if it is a file
			if zip_data and zip_name.lower().endswith(FILE_EXTENSION):
				log.info("File in zip detected! Name: %s - check for VBA" % (zip_name))
				# send to the checkFile
				self.checkFileforVBA(zip_data, zip_name, msg)

	def archive_message(self):
		'''
		Save a copy of the current message in its original form to a file
		:return: nothing
		'''
		date_time = datetime.datetime.utcnow().isoformat('_')
		# assumption: by combining datetime + milter id, the filename should be unique:
		# (the only case for duplicates is when restarting the milter twice in less than a second)
		fname = 'mail_%s_%d.eml' % (date_time, self.id)
		fname = os.path.join(ARCHIVE_DIR, fname)
		log.debug('Saving a copy of the original message to file %r' % fname)
		open(fname, 'wb').write(self.messageToParse.getvalue())

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

	def extract_all(self, input_zip):
		# TBD - extract_zip is not called !?
		return {entry: self.extract_zip(entry) for entry in ZipFile(input_zip).namelist() if is_zipfile(entry)}

	def extract_zip(self, input_zip):
		input_zip = ZipFile(input_zip)
		return {name: input_zip.read(name) for name in input_zip.namelist()}

## ===== END CLASS ========


## ==== start MAIN ========

def WhiteListLoad():
	'''
		Function to load the data form the WhiteList file and load into memory
	'''
	global WhiteList
	WhiteList = config.get("Whitelist", "Recipients")

def HashTableLoad():
	'''
		Load the hash info from file to memory
	'''
	# Load Hashs from file
	global hashtable
	hashtable = set(line.strip() for line in open(HASHTABLE_PATH, 'a+'))

def main():
	# Load the whitelist into memory
	WhiteListLoad()
	HashTableLoad()

	# make sure the log directory exists:
	try:
		os.makedirs(LOGFILE_DIR)
	except:
		pass
	# Add the log message handler to the logger
	# log to files rotating once a day:
	handler = logging.handlers.TimedRotatingFileHandler(LOGFILE_PATH, when='D', encoding='utf8')
	# create formatter and add it to the handlers
	formatter = logging.Formatter('%(asctime)s - %(levelname)8s: %(message)s')
	handler.setFormatter(formatter)
	log.addHandler(handler)

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
	print("%s MacroMilter startup - Version %s" % (time.strftime('%d.%b.%Y %H:%M:%S'), __version__ ))
	print('logging to file %s' % LOGFILE_PATH)

	log.info('Starting mraptor_milter v%s - listening on %s' % (__version__, SOCKET))
	log.debug('Python version: %s' % sys.version)
	sys.stdout.flush()
	# set the "last" fall back to ACCEPT if exception occur
	Milter.set_exception_policy(Milter.ACCEPT)

	# start the milter
	Milter.runmilter("MacroMilter", SOCKET, TIMEOUT)

	print("%s Macro milter shutdown" % time.strftime('%d.%b.%Y %H:%M:%S'))

if __name__ == "__main__":
	main()
