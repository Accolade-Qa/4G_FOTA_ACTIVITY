package com.aepl.atcu;

import com.aepl.atcu.util.LoginPacketInfo;
import org.junit.Assert;
import org.junit.Test;

public class SerialReaderTest {

    private static class TestableReader extends SerialReader {
        public TestableReader() {
            super("COM0", 9600); // port not opened or used
        }

        public void processLine(String line) {
            // use protected method inherited from SerialReader
            processInternalState(line);
        }
    }

    @Test
    public void stateAbbreviation_thenLogin_shouldSetFullState() throws Exception {
        TestableReader reader = new TestableReader();
        // supply the resolver so abbreviation mapping works (using same file as default)
        reader.setStateResolver(new com.aepl.atcu.logic.FirmwareResolver("input/servers.json"));
        reader.processLine(".  statewise prtcl    |  SWEMP     MH  - MH is abbreviation");
        // at this point reader.lastDeviceState should be "Maharashtra" (assuming servers.json contains that)
        LoginPacketInfo packet = new LoginPacketInfo("123456789012345", "ICCID", "ACON1", "v", "VIN", null, reader.lastDeviceState);
        // simulate a login packet parse
        reader.processLine("55AA,0,0,0,123456789012345,ICCID,ACON1,v,VIN");
        LoginPacketInfo saved = reader.getLastLoginPacketInfo();
        Assert.assertNotNull(saved);
        Assert.assertEquals("Maharashtra", reader.lastDeviceState);
        Assert.assertEquals("Maharashtra", saved.state);
    }
}