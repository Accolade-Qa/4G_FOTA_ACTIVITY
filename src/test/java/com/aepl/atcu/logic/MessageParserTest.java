package com.aepl.atcu.logic;

import org.junit.Test;
import org.junit.Assert;


public class MessageParserTest {

    @Test
    public void parseStatewiseLine_shouldExtractAbbreviation() {
        MessageParser parser = new MessageParser();
        String line = ".  statewise prtcl    |  SWEMP     MH  - MH is abbreviation";
        MessageParser.ParsedInfo info = parser.parse(line);
        Assert.assertNotNull(info);
        Assert.assertEquals("MH", info.state);
        Assert.assertEquals("STATEWISE", info.software);
        Assert.assertNull(info.version);
    }

    @Test
    public void parseNormalState_shouldReturnState() {
        MessageParser parser = new MessageParser();
        String line = "SOFTWARE: SWEMP STATE: STABLE VERSION: 5.2.9_REL06";
        MessageParser.ParsedInfo info = parser.parse(line);
        Assert.assertNotNull(info);
        Assert.assertEquals("STABLE", info.state);
        Assert.assertEquals("SWEMP", info.software);
        Assert.assertEquals("5.2.9_REL06", info.version);
    }

    @Test
    public void parseLoginPacket_withDeviceState_shouldPopulateState() {
        MessageParser parser = new MessageParser();
        // simulate that parser already knew the state (from previous lines)
        parser.setDeviceState("Maharashtra");
        // craft simple login packet line with enough fields
        String loginLine = "55AA,0,0,0,123456789012345,ICCID123,ACON0001,5.2.8_REL24,VIN123";
        MessageParser.ParsedInfo info = parser.parse(loginLine);
        Assert.assertNotNull(info);
        Assert.assertEquals("LOGIN", info.state);
        Assert.assertNotNull(info.loginPacketInfo);
        Assert.assertEquals("Maharashtra", info.loginPacketInfo.state);
        Assert.assertEquals("5.2.8_REL24", info.loginPacketInfo.version);
    }
}
