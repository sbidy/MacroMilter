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
## 2.8.1 - 30.03.2016 sbidy - Fix the str-exception, added some logging infomations
## 2.9 - 20.05.2016 sbidy - Fix issue #6 - queue not empty after log fiel cant written, write extension data to file deleted
## 2.9.1 - 20.05.2016 sbidy - Additional fixes for #6

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
import smtplib
import smtpd
import sys
import os
import io
import re
import hashlib
import zipfile
import tempfile

from zipfile import ZipFile, is_zipfile

from sets import Set
from oletools.olevba import VBA_Parser, TYPE_OLE, TYPE_OpenXML, TYPE_Word2003_XML, TYPE_MHTML
from socket import AF_INET, AF_INET6
from email.mime.text import MIMEText
from Queue import Empty

from Milter.utils import parse_addr
if True:
	from multiprocessing import Process as Thread, Queue
else:
	from threading import Thread
	from Queue import Queue
	

## Config (finals)
FILE_EXTENSION = ('.rtf','.docx','.xlsx','.xls', '.doc', '.docm', '.xlsm') # lower letter !! 
ZIP_EXTENSIONS = ('.zip')
MAX_FILESIZE = 50000000 # ~50MB
__version__ = '2.9.1' # version
REJECTLEVEL = 5 # Defines the max Macro Level (normal files < 10 // suspicious files > 10)

RAR_SUPPORT = True # or False # Requires unrar (apt-get install unrar) and "pip install rarfile"

# at to the postfix configuration -->  "smtpd_milters = inet:127.0.0.1:3690"
# see http://www.postfix.org/MILTER_README.html

SOCKET = "inet:10103@127.0.0.1" # bind to unix or tcp socket "inet:port@ip" or "/<path>/<to>/<something>.sock"
TIMEOUT = 30 # Milter timeout in seconds
CFG_DIR = "/etc/macromilter/"
LOG_DIR = "/var/log/macromilter/"
MESSAGE = "ERROR = Attachment contains unallowed office macros!"

## buffer queues for inter-thread communication 
logq = Queue(maxsize=10)
performace_data = Queue(maxsize=10)
hash_to_write = Queue(maxsize=10)
hashtable = Set()
## immutable state
WhiteList = None

## Customized milter class - partly copied from
## https://github.com/jmehnle/pymilter/blob/master/milter-template.py

class MacroMilter(Milter.Base):

	def __init__(self):  # A new instance with each new connection.
		self.id = Milter.uniqueID()  # Integer incremented with each call.
		self.fp = None
		self.level = 0
		self.headercount = 0
		self.macroflag = False
		self.size = 0 

	@Milter.noreply
	def connect(self, IPname, family, hostaddr):
		
	# define all vars
		#self.IP = hostaddr[0]
		#self.port = hostaddr[1]
		#if family == AF_INET6:
		#	self.flow = hostaddr[2]
		#	self.scope = hostaddr[3]
		#else:
		#	self.flow = None
		#	self.scope = None
		#self.IPname = IPname  # Name from a reverse IP lookup
		self.fp = None # content
		#self.receiver = self.getsymval('j') # not needed
		# self.log("connect from %s at %s" % (IPname, hostaddr)) # for logging
		return Milter.CONTINUE

	@Milter.noreply
	def envfrom(self, mailfrom, *str):
		self.fp = StringIO.StringIO()
		self.canon_from = '@'.join(parse_addr(mailfrom))
		self.fp.write('From %s %s\n' % (self.canon_from,time.ctime()))
		return Milter.CONTINUE

	@Milter.noreply
	def envrcpt(self, to, *str):
		return Milter.CONTINUE

	@Milter.noreply
	def header(self, name, hval):
		self.fp.write("%s: %s\n" % (name,hval))
		self.headcount = self.headercount+1
		return Milter.CONTINUE

	@Milter.noreply
	def eoh(self):
		self.fp.write("\n")
		return Milter.CONTINUE

	@Milter.noreply
	def body(self, chunk):
		self.fp.write(chunk)
		return Milter.CONTINUE

	# end of file - run the parser
	def eom(self):
		try:
		# set data pointer back to 0
			self.fp.seek(0)
			# start the timer
			self.start = time.time() # start timer for performance measuring
		# call the data parsing method
			result = self.parse(self.fp)
			if result is not None:
				# stop timer
				self.end = time.time()
				self.secs = self.end - self.start
				self.addData(self.secs, self.level)
				return result
			else:
				return Milter.ACCEPT
		#if error make a fall-back to accept
		except zipfile.BadZipfile, b:
			self.log("Unexpected error - No zip File REJECT: %s" % sys.exc_value)
			return Milter.REJECT
		except Exception, a:
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			self.log("Unexpected error - fall back to ACCEPT: %s %s %s" % (exc_type, fname, exc_tb.tb_lineno))
			return Milter.ACCEPT
		
	def close(self):
	# stop timer at close
		return Milter.CONTINUE
			
	def abort(self):
	# nothing to clean up
		return Milter.CONTINUE
	
## ==== Data processing ====

	def parse(self, data):
		'''
			parse the whole email data an check if there is a attachment
		'''
		# use the email 
		msg = email.message_from_string(data.getvalue())
		# Set Reject Message - definition from here
		# https://www.iana.org/assignments/smtp-enhanced-status-codes/smtp-enhanced-status-codes.xhtml
		self.setreply('550','5.7.1',MESSAGE)

		# return if no attachment
		if len(msg.get_payload()) < 2:
			return Milter.ACCEPT
		# if attachment get name
		
		i = 1
		while len(msg.get_payload()) > i:
			try:
				attachment = msg.get_payload()[i]
				filename = attachment.get_filename()
			except Exception, a:
				self.log("Cant read the attachment - SPAM ?!")
				# Set spam level
				# self.addheader("X-Spam-Flag","YES",self.headcount+1)
				# set flag to CONTINUE -> ACCEPT ??
				return Milter.CONTINUE
			# additional check if filename exists and file size is "nomal"
			if filename is not None:
				
				raw_data = attachment.get_payload(decode=True)
				# parse if the file is a zip
				if (filename.lower().endswith(ZIP_EXTENSIONS)):
					self.log("Find Attachment with extension - File content type: %s - File name: %s" % (attachment.get_content_type(),attachment.get_filename()))
					# issue #5
					self.checkZIPforVBA(raw_data,filename,msg)
				if (filename.lower().endswith(FILE_EXTENSION)):
					self.log("Find Attachment with extension - File content type: %s - File name: %s" % (attachment.get_content_type(),attachment.get_filename()))
					self.checkFileforVBA(raw_data,filename,msg)
				#if (filename.lower().endswith(".rar") and RAR_SUPPORT):
				#	self.checkRARforVBA(raw_data,filename,msg)
			else:
				# Filename can be read !!!  Fall back to accept
				if not self.macroflag:
					self.macroflag = False
			# inc 1 - loop walk
			i = i + 1

		if not self.macroflag :
			# Nothing found 
			return Milter.ACCEPT
		if self.macroflag:
			return Milter.REJECT

	def checkFileforVBA(self, data, filename, msg):
		'''
			Checks if it contains a vba macro and checks if user is whitelisted or file allready parsed
		'''
		# parse the data if it is file extension
		
		# Get sender name <SENERNAME>
		msg_from = re.findall('<([^"]*)>', msg['From'])
	
		# check sender name and return if at the whitelist
		if self.check_name(str(msg_from)):
			self.log("Whitelisted user %s - accept all attachments" % (msg_from))
			self.macroflag = False
			return
				
		# if sender is not whitelisted
		
		# generate Hash from file
		hash_data = hashlib.md5(data).hexdigest()
		# check if file is already parsed
		if hash_data in hashtable:
			self.log("Attachment %s already parsed ! REJECT" % hash_data)
			self.macroflag = True # reject
			return

		# sent to VBA parser
		report = self.doc_parsing(filename, data)
		self.log("VBA parsing exit")
		# Save log to disk and return reject because attachment contains vba Macro
		if report is not None:				
			# check if reject level is reached
			if self.level > REJECTLEVEL:
				# generate report for logfile >> <filename>.<extenstion>.log
				report += "\n\nFrom:%s\nTo:%s\n" % (msg['FROM'], msg['To'])
				# write log
				filename = filename + '.log'
				open(LOG_DIR+"log/"+filename,'w').write(report)

				# REJECT message and add to db file and memory
				hashtable.add(hash_data)
				hash_to_write.put(hash_data)
				self.log("Message rejected with Level: %d" % (self.level))
				self.log("File Added %s" % hash_data)
				self.macroflag = True # reject
				# if level is lower than configured
				return
			else:
				self.log("Message accepted with Level: %d - under configured threshold" % (self.level))
				if not self.macroflag:
					self.macroflag = False
					return
	
	def checkZIPforVBA(self, data, filename, msg):
		'''
			Checks a zip for parsable files and send to the parser
		'''
		file_object = StringIO.StringIO(data)
		#self.size = len(StringIO(data))
		#print "Size:"+self.size
		files_in_zip = self.extract_zip(file_object)
		for zip_name,zip_data in files_in_zip.items():
			# checks if it is a file
			if zip_data and zip_name.lower().endswith(FILE_EXTENSION):
				self.log("File in zip detected! Name: %s - check for VBA" % (zip_name))
				# send to the checkFile
				self.checkFileforVBA(zip_data,zip_name,msg)

	def checkRARforVBA(self, data, filename, msg):
		'''
			Creates a tmp file from the rar arcive (no in-memory support for rar possible)
		'''
		import rarfile

		file_size_limit = 500000
		rarfile.UNRAR_TOOL = "unrar"

		# create temp file
		tmpdir = tempfile.mkdtemp()
		# Ensure the file is read/write by the creator only
		saved_umask = os.umask(0077)
		path = os.path.join(tmpdir, filename)
		try:
			with open(path, "w") as tmp:
				tmp.write(data)
			with rarfile.RarFile(path) as rf:
				for f in rf.infolist():
					if f and f.filename.endswith(FILE_EXTENSION) and file_size_limit > f.file_size:
						self.log("File in rar detected! Name: %s - check for VBA" % (f.filename))
						rar_file = rf.read(f.filename)
						print rar_file
		except IOError as e:
			self.log("IOError at temp file !! %s" % path)
			return Milter.CONTINUE
		finally:
			os.remove(path)
			os.removedirs(tmpdir)

	def check_name(self, sender):
		'''
			Lookup if the sender is at the whitelist - @domains.com must be supported
		'''
		for name in WhiteList:
			if re.search(name,sender) and not name.startswith("#"): return True
		return False
	
	def doc_parsing(self, filename, filecontent):
		'''
			Function to parse the given data in mail content
		'''
		mil_attach = '' # reset var
		# send data to vba parser
		vbaparser = VBA_Parser(filename, data=filecontent)
		# if a macro is detected
		if vbaparser.detect_vba_macros():
			results = vbaparser.analyze_macros()
			nr = 1
			self.log("VBA Macros found")
			# generate report for log file
			for kw_type, keyword, description in results:
				if kw_type == 'Suspicious':
					mil_attach += 'Macro Number %i:\n Type: %s\n Keyword: %s\n Description: %s\n' % (nr, kw_type, keyword, description)
				nr += 1
			mil_attach += '\nSummery:\nAutoExec keywords: %d\n' % vbaparser.nb_autoexec
			mil_attach += 'Suspicious keywords: %d\n' % vbaparser.nb_suspicious
			mil_attach += 'IOCs: %d\n' % vbaparser.nb_iocs
			mil_attach += 'Hex obfuscated strings: %d\n' % vbaparser.nb_hexstrings
			mil_attach += 'Base64 obfuscated strings: %d\n' % vbaparser.nb_base64strings
			mil_attach += 'Dridex obfuscated strings: %d\n' % vbaparser.nb_dridexstrings
			mil_attach += 'VBA obfuscated strings: %d' % vbaparser.nb_vbastrings
			
			r_level = vbaparser.nb_autoexec + vbaparser.nb_suspicious + vbaparser.nb_iocs + vbaparser.nb_hexstrings + vbaparser.nb_base64strings + vbaparser.nb_dridexstrings + vbaparser.nb_vbastrings
			
			# set reject level to global
			self.level = r_level
			vbaparser.close()
			return mil_attach # return the log to caller
		else:
			self.log("VBA no Macros found in file")
			vbaparser.close()
			return None # nothing found
		
## === Support Functions ===

	def log(self,*msg):
		logq.put((msg,self.id,time.time()))
	def addData(self, *data):
		performace_data.put(data,self.level)
	def extract_all(self, input_zip): 
		# TBD - extract_zip is not called !?
		return {entry: self.extract_zip(entry) for entry in ZipFile(input_zip).namelist() if is_zipfile(entry)}
	def extract_zip(self, input_zip):
		input_zip=ZipFile(input_zip)
		return {name: input_zip.read(name) for name in input_zip.namelist()}
	
## ===== END CLASS ========


## ==== start MAIN ========
def writehashtofile():
	'''
		Write the hash to db file
	'''
	while True:	
		try:
			hash_data = hash_to_write.get()
			if not hash_data: break
			# check if hash is in loaded hashtable
			if hash_data not in hashtable:
				with open(LOG_DIR+"HashTable.dat", "a") as myfile:
					myfile.write(hash_data + '\n')
		except Exception, e:
			print "Cant write HashTable.dat"
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			print("Error at log file: %s %s %s" % (exc_type, fname, exc_tb.tb_lineno))

def background():
	'''
		Write the logging informations to stdout
	'''
	msg_log = LOG_DIR+'run.log'
	print msg_log
	while True:
		try:
			t = logq.get()
			if not t: break
			msg,id,ts = t
			for i in msg:
				text = "%s [%d] - %s" % (time.strftime('%d.%m.%y %H:%M:%S',time.localtime(ts)),id, i)
				text = text.encode('utf8')
				print text
				open(msg_log,'a+').write(text + '\n')
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
		try:
			data = performace_data.get()
			if not data: break
			latenz,level = data
			for d in data:
				text = "%f;%d;%s\n" % (latenz,level,time.strftime('%d/%m/%y %H:%M:%S',time.localtime(time.time())))
				open(LOG_DIR+'performace.data', 'a+').write(text)
		except Exception, e:
			print "Cant write run.log"
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			print("Error at log file: %s %s %s" % (exc_type, fname, exc_tb.tb_lineno))

		
## === StartUp sequence

def WhiteListLoad():
	'''
		Function to load the data form the WhiteList file and load into memory
	'''
	global WhiteList
	with open(CFG_DIR+'whitelist.list') as f:
		WhiteList = f.read().splitlines()

def HashTableLoad():
	'''
		Load the hash info from file to memory
	'''
	# Load Hashs from file
	global hashtable
	hashtable = set(line.strip() for line in open(LOG_DIR+'HashTable.dat','a+'))
	
def main():

	# Load the whitelist into memory
	WhiteListLoad()
	HashTableLoad()

	# create helper threads
	bt = Thread(target=background)
	perft = Thread(target=writeperformacedata)
	ha = Thread(target=writehashtofile)

	# start helper threads
	perft.start()
	bt.start()
	ha.start()

	# Register to have the Milter factory create instances of the class:
	Milter.factory = MacroMilter
	flags = Milter.CHGBODY + Milter.CHGHDRS + Milter.ADDHDRS
	flags += Milter.ADDRCPT
	flags += Milter.DELRCPT
	Milter.set_flags(flags)       # tell Sendmail which features we use
	# start milter processing
	print "%s Macro milter startup - Version %s" % (time.strftime('%d.%b.%Y %H:%M:%S'), __version__)
	sys.stdout.flush()
	# set the "last" fall back to ACCEPT if exception occur
	Milter.set_exception_policy(Milter.ACCEPT)

	# start the milter
	Milter.runmilter("MacroMilter",SOCKET,TIMEOUT)
	
	# wait for helper threads
	bt.join() # stop logging thread
	perft.join() # stop performance data thread
	ha.join() # stop hash data thread

	# cleanup the queues
	logq.put(None)
	hash_to_write.put(None)
	performace_data.put(None)

	print "%s Macro milter shutdown" % time.strftime('%d.%b.%Y %H:%M:%S')
	
if __name__ == "__main__":
	main()
	
