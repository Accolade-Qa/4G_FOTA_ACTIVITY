package com.aepl.atcu;

import com.aepl.atcu.util.LoginPacketInfo;
import org.junit.Test;

import static org.junit.Assert.*;

public class SerialReaderTest {

    @Test
    public void testLoginPacketCapturedOnce() {
        SerialReader reader = new SerialReader("COM_TEST", 9600);

        LoginPacketInfo first = new LoginPacketInfo("imei1","iccid1","uin1","ver1","vin1","model1","state1");
        reader.captureLoginPacket(first);
        assertSame("first packet should be stored", first, reader.getLastLoginPacketInfo());

        LoginPacketInfo second = new LoginPacketInfo("imei2","iccid2","uin2","ver2","vin2","model2","state2");
        reader.captureLoginPacket(second);
        assertSame("subsequent capture should be ignored", first, reader.getLastLoginPacketInfo());

        reader.resetState();
        assertNull("state reset should clear stored packet", reader.getLastLoginPacketInfo());

        reader.captureLoginPacket(second);
        assertSame("after reset new packet can be stored", second, reader.getLastLoginPacketInfo());
    }
}
