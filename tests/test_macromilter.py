import StringIO

import pytest
import os
import sys


from test_classes import TestBase

sys.path.insert(0, os.path.abspath('..'))

from macromilter import macromilter
import Milter

TEST_MAIL_FOLDER = 'tests/test_mails'

thread_pool = []

@pytest.fixture(scope="function")
def macromilterSUT(request):

    macromilter.LOG_DIR = 'test_output/'
    macromilter.initialize_async_process_queues(20)
    macromilter.cleanup_queues()

    Milter.factory = macromilter.MacroMilter
    flags = Milter.CHGBODY + Milter.CHGHDRS + Milter.ADDHDRS
    flags += Milter.ADDRCPT
    flags += Milter.DELRCPT
    Milter.set_flags(flags)
    Milter.factory._ctx = TestBase()

    sut = macromilter.MacroMilter()
    sut.messageToParse = StringIO.StringIO()

    def tear_down():
        # clear queues
        macromilter.cleanup_queues()
        print "tear down called"



    request.addfinalizer(tear_down)

    return sut



class TestErrorFallback:
    def test_EmptyMessageShouldFallbackToAccept(self, macromilterSUT):

        result = macromilterSUT.parseAndCheckMessageAttachment()
        assert result == Milter.ACCEPT

    def test_milterMailWithoutAttachmentShouldAccept(self, macromilterSUT):

        self.loadTestMailInto(macromilterSUT, "01_mail_without_attachment.eml")
        result = macromilterSUT.parseAndCheckMessageAttachment()
        assert result == Milter.ACCEPT

    def test_matchWordFileShouldReject(self, macromilterSUT):
        self.loadTestMailInto(macromilterSUT, "02_mail_with_infected_word_document.eml")
        result = macromilterSUT.parseAndCheckMessageAttachment()
        assert macromilterSUT.attachment_contains_macro == True
        assert result == Milter.REJECT


    def test_matchZipWithInfectedWordFileShouldReject(self, macromilterSUT):
        self.loadTestMailInto(macromilterSUT, "03_mail_with_infected_word_in_zip.eml")

        result = macromilterSUT.parseAndCheckMessageAttachment()
        assert macromilterSUT.attachment_contains_macro == True
        assert result == Milter.REJECT

    def test_matchCleanZipAndInfectedWordFileShouldReject(self, macromilterSUT):
        '''two files as attachment: 1 clean zip, 1 infected word'''
        self.loadTestMailInto(macromilterSUT, "04_mail_with_infected_word_and_clean_zip.eml")

        result = macromilterSUT.parseAndCheckMessageAttachment()
        assert macromilterSUT.attachment_contains_macro == True
        assert result == Milter.REJECT


    # zip mit infected und clean
    def test_matchCleanAndInfectedInZipShouldReject(self, macromilterSUT):
        '''two files as attachment: 1 clean zip, 1 infected word'''
        self.loadTestMailInto(macromilterSUT, "05_mail_with_both_infected_and_not_word_in_zip.eml")

        result = macromilterSUT.parseAndCheckMessageAttachment()
        assert macromilterSUT.attachment_contains_macro == True
        assert result == Milter.REJECT



    # zip with zip having infected word

    # zip with zip having clean word

    def loadTestMailInto(self, sut, test_mailfile):
        testMailFileHandle = open(TEST_MAIL_FOLDER + "/"+ test_mailfile)
        mailContent = testMailFileHandle.read()
        testMailFileHandle.close()
        sut.messageToParse.write(mailContent)



# testSendCleanDocumentShouldPass

# testSendInfectedWordShouldBeRejected

# testSendInfectedExcelShouldBeRejected

# testSendInfectedZipShouldBeRejected

# testSendInfectedRarShouldBeRejected

# testSendMailCausingErrorShouldPass
