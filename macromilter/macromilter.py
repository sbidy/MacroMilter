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
from _socket import AF_INET6

import Milter
import StringIO
import time
import email
import sys
import re
import hashlib
import zipfile
from zipfile import ZipFile, is_zipfile
import os
import errno

from sets import Set
from oletools.olevba import VBA_Parser, TYPE_OLE, TYPE_OpenXML, TYPE_Word2003_XML, TYPE_MHTML
from socket import AF_INET6

from Milter.utils import parse_addr

if True:
	from multiprocessing import Process as Thread, Queue
else:
	from threading import Thread
	from Queue import Queue
from Queue import Empty

## Config (finals)
FILE_EXTENSION = ('.rtf', '.xls', '.doc', '.docm', '.xlsm')  # lower letter !!
ZIP_EXTENSIONS = ('.zip')
MAX_FILESIZE = 50000000  # ~50MB
__version__ = '2.8.1'  # version
REJECTLEVEL = 5  # Defines the max Macro Level (normal files < 10 // suspicious files > 10)
# at postfix smtpd_milters = inet:127.0.0.1:3690
SOCKET = "inet:3690@127.0.0.1"  # bind to unix or tcp socket "inet:port@ip" or "/<path>/<to>/<something>.sock"
TIMEOUT = 30  # Milter timeout in seconds
CFG_DIR = "/etc/macromilter/"
LOG_DIR = "/var/log/macromilter/"
MATCHED_FILE_LOG_DIR = LOG_DIR + "/matched_files/"
WHITELIST_FILE = CFG_DIR + "whitelist.list"
MESSAGE = "ERROR = Attachment contains unallowed office macros!"


logq = None
performace_data = None
extension_data = None
hash_to_write = None
hashtable = None
WhiteList = None



## Customized milter class - partly copied from
## https://github.com/jmehnle/pymilter/blob/master/milter-template.py


class MacroMilterBase(Milter.Base):
	'''Base class for MacroMilter to move boilerplate connection stuff away from the real
		business logic for macro parsing
	'''
	def __init__(self):  # A new instance with each new connection.
		self.id = Milter.uniqueID()  # Integer incremented with each call.
		self.messageToParse = None
		self.level = 0
		self.headercount = 0
		self.attachment_contains_macro = False
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
		# self.log("connect from %s at %s" % (IPname, hostaddr)) # for logging
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
		self.headcount = self.headercount + 1
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

	def log(self, *msg):
		logq.put((msg, self.id, time.time()))

	def mkdir_p(self, path):
		try:
			os.makedirs(path)
		except OSError as exc:  # Python >2.5
			if exc.errno == errno.EEXIST and os.path.isdir(path):
				pass
			else:
				raise


class MacroMilter(MacroMilterBase):
	'''See MacroMilterBase for milter connection handling'''

	# end of file - run the parser
	def eom(self):
		'''This method is called when the end of the email message has been reached.
		   This event also triggers the milter specific actions
		'''
		try:
			# set data pointer back to 0
			self.messageToParse.seek(0)
			# start the timer
			self.start = time.time()  # start timer for performance measuring
			# call the data parsing method
			result = self.parseAndCheckMessageAttachment()
			if result is not None:
				# stop timer
				self.end = time.time()
				self.secs = self.end - self.start
				self.addData(self.secs, self.level)
				return result
			else:
				return Milter.ACCEPT
				# if error make a fall-back to accept
		except zipfile.BadZipfile, b:
			self.log("Unexpected error - No zip File REJECT: %s" % sys.exc_value)
			return Milter.REJECT
		except Exception, a:
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			self.log("Unexpected error - fall back to ACCEPT: %s %s %s" % (exc_type, fname, exc_tb.tb_lineno))
			return Milter.ACCEPT

	## ==== Data processing ====

	def parseAndCheckMessageAttachment(self):
		'''
			parse the whole email data an check if there is a attachment
		'''
		# use email from package email to parse the message string
		msg = email.message_from_string(self.messageToParse.getvalue())
		# Set Reject Message - definition from here
		# https://www.iana.org/assignments/smtp-enhanced-status-codes/smtp-enhanced-status-codes.xhtml
		self.setreply('550', '5.7.1', MESSAGE)

		self.attachment_contains_macro = False

		if self.sender_is_in_whitelist(msg):
			self.attachment_contains_macro = False
		else:
			if len(msg.get_payload()) >= 2:
				self.checkAttachment(msg)


		if self.attachment_contains_macro:
			return Milter.REJECT
		else:
			return Milter.ACCEPT


	def checkAttachment(self, msg):
		i = 1
		while len(msg.get_payload()) > i:

			attachment = msg.get_payload()[i]
			filename = attachment.get_filename()

			if filename is None:
				i = i + 1
				continue

			raw_data = attachment.get_payload(decode=True)

			# parse if the file is a zip
			if (filename.lower().endswith(ZIP_EXTENSIONS)):
				self.checkZIPforVBA(raw_data, filename, msg)
			else:
				self.checkFileforVBA(raw_data, filename, msg)

			i = i + 1

	def fileHasAlreadyBeenParsed(self, data):
		# generate Hash from file
		hash_data = hashlib.md5(data).hexdigest()
		# check if file is already parsed
		if hash_data in hashtable:
			self.log("Attachment %s already parsed ! REJECT" % hash_data)
			return True
		else:
			return False

	def addHashOfInfectedFileToDbAndFile(self, data):
		hash_data = hashlib.md5(data).hexdigest()
		hashtable.add(hash_data)
		hash_to_write.put(hash_data)

		self.log("File Added %s" % hash_data)

	def checkFileforVBA(self, data, filename, msg):
		'''
			Checks if it contains a vba macro and checks if user is whitelisted or file already parsed
		'''
		if not filename.lower().endswith(FILE_EXTENSION):
			return
		self.log("Attachment with matching file extension found: %s" % (filename))

		if self.fileHasAlreadyBeenParsed(data):
			self.attachment_contains_macro = True
			return

		# sent to VBA parser
		parsing_result = self.inspect_vba_data(filename, data)

		# Save log to disk and return reject because attachment contains vba Macro
		if parsing_result is not None:
			# check if reject level is reached
			self.level = parsing_result[0]
			report = parsing_result[1]

			if self.level > REJECTLEVEL:
				# generate report for logfile >> <filename>.<extenstion>.log
				report += "\n\nFrom:%s\nTo:%s\n" % (msg['FROM'], msg['To'])
				# write log
				self.writeMatchedVba2Logfile(filename, report)

				# REJECT message and add to db file and memory
				self.log("Message rejected with Level: %d" % self.level)
				self.addHashOfInfectedFileToDbAndFile(data)

				self.attachment_contains_macro = True  # reject
				# if level is lower than configured
				return
			else:
				self.log("Message accepted with Level: %d - under configured threshold" % (self.level))
				if not self.attachment_contains_macro:
					self.attachment_contains_macro = False
					return

	def writeMatchedVba2Logfile(self, filename, report):
		filename = filename + '.log'
		self.mkdir_p(MATCHED_FILE_LOG_DIR)
		report_logfile_handle = open(MATCHED_FILE_LOG_DIR + filename, 'w')
		report_logfile_handle.write(report)
		report_logfile_handle.close()

	def checkZIPforVBA(self, data, filename, msg):
		'''
			Checks a zip for parsesable files and send to the parser
		'''
		self.log("Find Attachment with archive extension - File name: %s" % (filename))

		file_object = StringIO.StringIO(data)
		# self.size = len(StringIO(data))
		# print "Size:"+self.size
		files_in_zip = self.extract_zip(file_object)
		for zip_name, zip_data in files_in_zip.items():
			# checks if it is a file
			if zip_data and zip_name.lower().endswith(FILE_EXTENSION):
				self.log("File in zip detected! Name: %s - check for VBA" % (zip_name))
				# send to the checkFile
				self.checkFileforVBA(zip_data, zip_name, msg)

	def sender_is_in_whitelist(self, msg):
		'''
			Lookup if the sender is at the whitelist - @domains.com must be supported
		'''
		sender = ''
		msg_from = msg['From']
		if msg_from is not None:
			sender = str(re.findall('<([^"]*)>', msg_from ))

		if WhiteList is not None:
			for name in WhiteList:
				if re.search(name, sender) and not name.startswith("#"):
					self.log("Whitelisted user %s - accept all attachments" % (msg_from))
					return True
		return False

	def inspect_vba_data(self, filename, filecontent):
		'''
			Function to parse the given data in mail content
		'''
		vbaparser_report_log = ''  # reset var
		# send data to vba parser
		vbaparser = VBA_Parser(filename, data=filecontent)
		# if a macro is detected
		if not vbaparser.detect_vba_macros():
			self.log("VBA no Macros found in file")
			vbaparser.close()
			return None  # nothing found
		else:
			results = vbaparser.analyze_macros()
			nr = 1
			self.log("VBA Macros found")
			# generate report for log file
			for kw_type, keyword, description in results:
				if kw_type == 'Suspicious':
					vbaparser_report_log += 'Macro Number %i:\n Type: %s\n Keyword: %s\n Description: %s\n' % (
					nr, kw_type, keyword, description)
				nr += 1
			vbaparser_report_log += '\nSummery:\nAutoExec keywords: %d\n' % vbaparser.nb_autoexec
			vbaparser_report_log += 'Suspicious keywords: %d\n' % vbaparser.nb_suspicious
			vbaparser_report_log += 'IOCs: %d\n' % vbaparser.nb_iocs
			vbaparser_report_log += 'Hex obfuscated strings: %d\n' % vbaparser.nb_hexstrings
			vbaparser_report_log += 'Base64 obfuscated strings: %d\n' % vbaparser.nb_base64strings
			vbaparser_report_log += 'Dridex obfuscated strings: %d\n' % vbaparser.nb_dridexstrings
			vbaparser_report_log += 'VBA obfuscated strings: %d' % vbaparser.nb_vbastrings

			r_level = vbaparser.nb_autoexec + vbaparser.nb_suspicious + vbaparser.nb_iocs + vbaparser.nb_hexstrings + vbaparser.nb_base64strings + vbaparser.nb_dridexstrings + vbaparser.nb_vbastrings

			# set reject level to global
			#self.level = r_level
			vbaparser.close()
			return [r_level, vbaparser_report_log]  # return the log to caller

		## === Support Functions ===

	def addData(self, *data):
		performace_data.put(data, self.level)

	def extract_all(self, input_zip):
		# TBD - extract_zip is not called !?
		return {entry: self.extract_zip(entry) for entry in ZipFile(input_zip).namelist() if is_zipfile(entry)}

	def extract_zip(self, input_zip):
		input_zip = ZipFile(input_zip)
		return {name: input_zip.read(name) for name in input_zip.namelist()}

## ===== END CLASS ========


## ==== start MAIN ========

def writehashtofile():
	'''
		Write the hash to db file
	'''
	while True:
		hash_data = hash_to_write.get()
		if not hash_data: break
		# check if hash is in loaded hashtable
		if hash_data not in hashtable:
			with open(LOG_DIR + "HashTable.dat", "a") as myfile:
				myfile.write(hash_data + '\n')

def initialize_async_process_queues(queuesize = 4):
	global logq, performace_data, extension_data, hash_to_write, hashtable, WhiteList
	## buffer queues for inter-thread communication

	logq = Queue(maxsize=queuesize) if (logq == None) else logq
	performace_data = Queue(maxsize=queuesize) if (performace_data == None) else performace_data
	extension_data = Queue(maxsize=queuesize) if (extension_data == None) else extension_data
	hash_to_write = Queue(maxsize=queuesize) if (hash_to_write == None) else extension_data
	hashtable = Set()


def create_and_start_worker_threads():
	#initialize_async_process_queues()
	thread_pool = []
	# create helper threads
	thread_pool.append(Thread(target=listen_on_logqueue_and_write_logging_to_stdout))
	#logq.put("log writer thread started")
	thread_pool.append(Thread(target=writeperformacedata))
	thread_pool.append(Thread(target=writehashtofile))
	# start helper threads
	for workerThread in thread_pool:
		workerThread.start()

	return thread_pool


def shutdown_worker_threads(thread_pool):
	# wait for helper threads
	for workerThread in thread_pool:
		workerThread.join()

def cleanup_queues():
	# cleanup the queues
	logq.put(None)
	hash_to_write.put(None)
	performace_data.put(None)

	clear_queue(logq)
	clear_queue(hash_to_write)
	clear_queue(performace_data)


def clear_queue(queue):
	try:
		while True:
			queue.get_nowait()
	except Empty:
		pass

def listen_on_logqueue_and_write_logging_to_stdout():
	'''
		Write the logging informations to stdout
	'''
	msg_log = LOG_DIR + 'run.log'
	print "macromilter: logging into " + msg_log
	while True:
		try:
			t = logq.get()
			if not t: break
			msg, id, ts = t
			for i in msg:
				text = "%s [%d] - %s" % (time.strftime('%d.%m.%y %H:%M:%S', time.localtime(ts)), id, i)
				print text
				open(msg_log, 'a+').write(text + '\n')
		except Exception, e:
			print "Cant write run.log"
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			print("Error at log file: %s %s %s" % (exc_type, fname, exc_tb.tb_lineno))


def writeperformacedata():
	'''
		Write the performance data to file in separate thread
	'''
	while True:
		data = performace_data.get()
		if not data: break
		latenz, level = data
		for d in data:
			text = "%f;%d;%s\n" % (latenz, level, time.strftime('%d/%m/%y %H:%M:%S', time.localtime(time.time())))
			open(LOG_DIR + 'performace.data', 'a+').write(text)


## === StartUp sequence

def WhiteListLoad():
	'''
		Function to load the data form the WhiteList file and load into memory
	'''
	global WhiteList
	with open(WHITELIST_FILE) as f:
		WhiteList = f.read().splitlines()


def HashTableLoad():
	'''
		Load the hash info from file to memory
	'''
	# Load Hashs from file
	global hashtable
	hashtable = set(line.strip() for line in open(LOG_DIR + 'HashTable.dat', 'a+'))


def main():
	# Load the whitelist into memory
	WhiteListLoad()
	HashTableLoad()

	thread_pool = create_and_start_worker_threads()

	# Register to have the Milter factory create instances of the class:
	Milter.factory = MacroMilter
	flags = Milter.CHGBODY + Milter.CHGHDRS + Milter.ADDHDRS
	flags += Milter.ADDRCPT
	flags += Milter.DELRCPT
	Milter.set_flags(flags)  # tell Sendmail which features we use
	# start milter processing
	print "%s Macro milter startup - Version %s" % (time.strftime('%d.%b.%Y %H:%M:%S'), __version__)
	sys.stdout.flush()
	# set the "last" fall back to ACCEPT if exception occur
	Milter.set_exception_policy(Milter.ACCEPT)

	# start the milter
	Milter.runmilter("MacroMilter", SOCKET, TIMEOUT)

	shutdown_worker_threads(thread_pool)
	cleanup_queues()

	print "%s Macro milter shutdown" % time.strftime('%d.%b.%Y %H:%M:%S')


if __name__ == "__main__":
	main()
