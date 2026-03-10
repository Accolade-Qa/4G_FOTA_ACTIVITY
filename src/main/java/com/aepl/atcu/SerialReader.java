package com.aepl.atcu;

import java.util.Scanner;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;

import com.aepl.atcu.logging.LogWriter;
import com.aepl.atcu.logic.MessageParser;
import com.aepl.atcu.serial.SerialConnection;
import com.aepl.atcu.util.LoginPacketInfo;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class SerialReader {

	private static final Logger logger = LogManager.getLogger(SerialReader.class);
	private final SerialConnection connection;
	private final LogWriter logWriter;
	private final MessageParser parser;
	private final BlockingQueue<String> processorQueue = new LinkedBlockingQueue<>(20000);
	private final StringBuilder lineBuffer = new StringBuilder();
	private volatile boolean running = false;
	private Thread inputThread;
	private double lastDownloadProgress = 0.0;
	private String lastSoftwareVersion = null;
	private String lastAeplFwVersion = null;
	private String lastDeviceId = null;
	private String lastDeviceState = null;
	private LoginPacketInfo lastLoginPacketInfo = null;
	private boolean loginPacketCaptured = false;
	private boolean aeplFwVerFound = false;

	public SerialReader(String portName, int baud) {
		this.connection = new SerialConnection(portName, baud);
		this.logWriter = new LogWriter();
		this.parser = new MessageParser();
		this.connection.setDataCallback(this::handleIncomingChunk);
	}

	public void start() {
		if (!connection.open()) {
			String errMsg = "Failed to open port. Tried: " + connection.getAttemptedPortsSummary();
			logger.error(errMsg);
			throw new RuntimeException(errMsg);
		}
		logger.info("Opened {}", connection.getSystemPortName());
		running = true;

		logWriter.start();

		inputThread = new Thread(this::terminalInputLoop, "terminal-input");
		inputThread.setDaemon(true);
		inputThread.start();

		Runtime.getRuntime().addShutdownHook(new Thread(() -> {
			stop();
			logger.info("Shutdown complete.");
		}));
	}
	public void stop() {
		running = false;
		if (inputThread != null) {
			inputThread.interrupt();
		}
		connection.close();
		logWriter.close();
	}

	private void handleIncomingChunk(String chunk) {
		if (chunk == null || chunk.isEmpty())
			return;
		synchronized (lineBuffer) {
			chunk = chunk.replace("\r\n", "\n").replace('\r', '\n');
			lineBuffer.append(chunk);
			int newlineIndex;
			while ((newlineIndex = lineBuffer.indexOf("\n")) != -1) {
				String rawLine = lineBuffer.substring(0, newlineIndex);
				lineBuffer.delete(0, newlineIndex + 1);

				String cleaned = parser.stripAnsi(rawLine).trim();
				if (!cleaned.isEmpty()) {
					logWriter.log(cleaned);

					boolean pOk = processorQueue.offer(cleaned);
					if (!pOk) {
						logger.warn("Processor Queue full: dropping line");
					}

					processProgress(cleaned);
					try {
						processInternalState(cleaned);
					} catch (Exception e) {
						logger.error("[SR] Failed while processing line '{}': {}", cleaned, e.getMessage(), e);
					}
				}
			}
		}
	}


	private void processProgress(String line) {
		Double progress = parser.parseDownloadProgress(line);
		if (progress != null) {
			this.lastDownloadProgress = progress;
			if (((int) (progress * 100)) % 500 == 0) {
				logger.info("[PROGRESS] Downloading: {}%", progress);
			}
		}
	}
	private void processInternalState(String line) {
		MessageParser.ParsedInfo info = parser.parse(line);
		if (info != null) {
			// If we found aeplFwVer (which returns software="SOFTWARE"), mark it as found
			if ("SOFTWARE".equals(info.software) && line.toLowerCase().contains("aeplfwver")) {
				this.aeplFwVerFound = true;
				this.lastAeplFwVersion = info.version;
				logger.info("[SR] High-fidelity AEPL FW Version found: {}", info.version);
			}

			this.lastSoftwareVersion = info.version;
			this.lastDeviceState = info.state; // Store the parsed state
			if (info.software != null && !info.software.equals("SOFTWARE") && !info.software.equals("FIRMWARE")) {
				this.lastDeviceId = info.software;
			}
			
			if (info.loginPacketInfo != null) {
				// only capture the first login packet until state is reset
				captureLoginPacket(info.loginPacketInfo);
			}
		}
	}

	public BlockingQueue<String> getProcessorQueue() {
		return this.processorQueue;
	}

	public double getLastDownloadProgress() {
		return lastDownloadProgress;
	}

	public String getLastSoftwareVersion() {
		return lastSoftwareVersion;
	}

	public String getLastAeplFwVersion() {
		return lastAeplFwVersion;
	}

	public String getLastDeviceId() {
		return lastDeviceId;
	}

	public LoginPacketInfo getLastLoginPacketInfo() {
		return lastLoginPacketInfo;
	}

	public String getLastDeviceState() {
		return lastDeviceState;
	}

	public void resetState() {
		this.lastSoftwareVersion = null;
		this.lastAeplFwVersion = null;
		this.lastDownloadProgress = 0.0;
		this.lastDeviceState = null;
		this.lastLoginPacketInfo = null;
		this.loginPacketCaptured = false;
		this.aeplFwVerFound = false;
		logger.info("[SR] State reset for new cycle.");
	}

	public void sendCommand(String cmd) {
		connection.writeEvent(cmd);
	}

	public boolean isAeplFwVerFound() {
		return aeplFwVerFound;
	}

	void captureLoginPacket(LoginPacketInfo info) {
		if (!loginPacketCaptured) {
			this.lastLoginPacketInfo = info;
			loginPacketCaptured = true;
			if (info.imei != null && !info.imei.isEmpty()) {
				logWriter.setImei(info.imei);
			}
		}
	}

	private void terminalInputLoop() {
		try (Scanner scanner = new Scanner(System.in)) {
			logger.info("[INPUT] Type commands. 'exit' to stop.");
			while (running) {
				if (!scanner.hasNextLine()) {
					Thread.sleep(50);
					continue;
				}
				String cmd = scanner.nextLine();
				if (cmd == null)
					continue;
				String trimmed = cmd.trim();
				if (trimmed.equalsIgnoreCase("exit") || trimmed.equalsIgnoreCase("quit")) {
					logger.info("Exiting...");
					stop();
					break; // Exit the loop instead of terminating JVM
				}
				logger.info("[SEND] {}", cmd);
				connection.writeEvent(cmd);
			}
		} catch (Exception e) {
			logger.error("Error in terminal input loop: {}", e.getMessage(), e);
		}
	}

}
