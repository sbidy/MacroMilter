import StringIO

import pytest
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

from macromilter import macromilter
import Milter


@pytest.fixture(scope="module")
def getMacromilterSUT():

    Milter.factory = macromilter.MacroMilter
    flags = Milter.CHGBODY + Milter.CHGHDRS + Milter.ADDHDRS
    flags += Milter.ADDRCPT
    flags += Milter.DELRCPT
    Milter.set_flags(flags)

    return macromilter.MacroMilter()


class TestErrorFallback:
    def test_ThrownExceptionShouldFallbackToPostfixAccept(self):
        #assert macromilter.parse(data) == Milter.Accept
        #macrom = macromilter.MacroMilter()
        #macrom.parse("dat")
        sut = getMacromilterSUT()
        sut.messageToParse = StringIO.StringIO()

        result = sut.parseAndCheckMessageAttachment()
        assert result == Milter.Accept


# testSendCleanDocumentShouldPass

#testSendInfectedWordShouldBeRejected

#testSendInfectedExcelShouldBeRejected

#testSendInfectedZipShouldBeRejected

#testSendInfectedRarShouldBeRejected

#testSendMailCausingErrorShouldPass
