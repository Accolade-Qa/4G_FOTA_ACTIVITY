package com.aepl.atcu;

import com.aepl.atcu.util.LoginPacketInfo;
import org.junit.Test;

import java.util.LinkedList;
import java.util.Queue;

import static org.junit.Assert.*;

public class OrchestratorTest {

    /**
     * Simple stub that allows us to emulate a series of login packets when
     * waitForLoginPacket is invoked. We also expose a mutable progress value.
     */
    static class StubSerialReader extends SerialReader {
        private double progress = 0.0;

        public StubSerialReader() {
            super("COM_TEST", 0);
        }

        void setProgress(double p) {
            this.progress = p;
        }

        @Override
        public double getLastDownloadProgress() {
            return progress;
        }
    }

    static class TestOrchestrator extends Orchestrator {
        private final Queue<LoginPacketInfo> loginQueue = new LinkedList<>();
        StubSerialReader stubReader;

        public TestOrchestrator(StubSerialReader reader, String auditCsv, String firmwareJson,
                String defaultState, String loginJson) throws Exception {
            super(reader, auditCsv, firmwareJson, defaultState, loginJson);
            this.stubReader = reader;
        }

        void queueLogin(LoginPacketInfo info) {
            loginQueue.add(info);
        }

        @Override
        LoginPacketInfo waitForLoginPacket(int timeoutSeconds) {
            // return next available packet; null if none
            return loginQueue.poll();
        }
    }

    @Test
    public void monitorDownloadProgress_honoursFinalVersion() throws Exception {
        StubSerialReader reader = new StubSerialReader();
        TestOrchestrator orch = new TestOrchestrator(reader, "audit", "firmware.json", "XX", "login.json");

        // prepare wrong then right packet
        LoginPacketInfo wrong = new LoginPacketInfo("i", "c", "u", "1.0", "v", "m", "s");
        LoginPacketInfo right = new LoginPacketInfo("i", "c", "u", "2.0", "v", "m", "s");
        orch.queueLogin(wrong);
        orch.queueLogin(right);

        // simulate that progress has finished
        reader.setProgress(100.0);

        boolean ok = orch.monitorDownloadProgress("batch", "2.0");
        assertTrue("should return true once final version seen", ok);
    }

    @Test
    public void monitorDownloadProgress_failsIfVersionNeverArrives() throws Exception {
        StubSerialReader reader = new StubSerialReader();
        TestOrchestrator orch = new TestOrchestrator(reader, "audit", "firmware.json", "XX", "login.json");

        // queue only wrong version
        LoginPacketInfo wrong = new LoginPacketInfo("i", "c", "u", "1.0", "v", "m", "s");
        orch.queueLogin(wrong);

        reader.setProgress(100.0);
        boolean ok = orch.monitorDownloadProgress("batch", "2.0");
        assertFalse("should return false when target version never seen", ok);
    }
}
