package com.aepl.atcu;

import java.util.Scanner;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.LinkedBlockingQueue;

import com.aepl.atcu.logging.LogWriter;
import com.aepl.atcu.logic.MessageParser;
import com.aepl.atcu.serial.SerialConnection;
import com.aepl.atcu.util.LoginPacketInfo;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Controller class for managing device serial communication.
 * It acts as a facade connecting physical transport (SerialConnection),
 * business logic (MessageParser), and persistent logging (LogWriter).
 * 
 * NOTE: This class handles asynchronous incoming data chunks, assembles them
 * into full lines,
 * and updates an internal state map representing the current device status.
 */
public class SerialReader {

	private static final Logger logger = LogManager.getLogger(SerialReader.class);
	private final SerialConnection connection;
	private final LogWriter logWriter;
	private final MessageParser parser;

	private final BlockingQueue<String> processorQueue = new LinkedBlockingQueue<>(20000);
	private final ConcurrentMap<String, ConcurrentMap<String, String>> stateMap = new ConcurrentHashMap<>();
	private final StringBuilder lineBuffer = new StringBuilder();

	private double lastDownloadProgress = 0.0;
	private String lastSoftwareVersion = null;
	private String lastAeplFwVersion = null;
	private String lastDeviceId = null;
	private String lastDeviceState = null;
	private LoginPacketInfo lastLoginPacketInfo = null;
	private boolean aeplFwVerFound = false;

	// optional resolver used to map state abbreviations to full names
	private com.aepl.atcu.logic.FirmwareResolver stateResolver = null;

	/**
	 * Initializes the SerialReader with connection parameters.
	 * 
	 * @param portName The system name of the serial port (e.g., COM3)
	 * @param baud     The communication baud rate
	 */
	public SerialReader(String portName, int baud) {
		this.connection = new SerialConnection(portName, baud);
		this.logWriter = new LogWriter();
		this.parser = new MessageParser();
		this.connection.setDataCallback(this::handleIncomingChunk);
	}

	/**
	 * Opens the serial port, starts internal logging, and begins the terminal input
	 * loop.
	 * 
	 * @throws RuntimeException If the serial port cannot be opened
	 */
	public void start() {
		if (!connection.open()) {
			String errMsg = "Failed to open port. Tried: " + connection.getAttemptedPortsSummary();
			logger.error(errMsg);
			throw new RuntimeException(errMsg);
		}
		logger.info("Opened {}", connection.getSystemPortName());

		logWriter.start();

		Thread inputThread = new Thread(this::terminalInputLoop, "terminal-input");
		inputThread.setDaemon(false);
		inputThread.start();

		Runtime.getRuntime().addShutdownHook(new Thread(() -> {
			stop();
			logger.info("Shutdown complete.");
		}));
	}

	/**
	 * Gracefully closes the serial connection and stops the log writer.
	 */
	public void stop() {
		connection.close();
		logWriter.close();
	}

	/**
	 * Internal callback to process raw data chunks from the serial port.
	 * Assembles chunks into lines and passes them to the log writer and parser.
	 * 
	 * @param chunk The raw string fragment received from serial
	 */
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
					processInternalState(cleaned);
				}
			}
		}
	}

	/**
	 * Parses and updates the last known download progress from a log line.
	 * 
	 * @param line The cleaned log line from the device
	 */
	private void processProgress(String line) {
		Double progress = parser.parseDownloadProgress(line);
		if (progress != null) {
			this.lastDownloadProgress = progress;
			if (((int) (progress * 100)) % 500 == 0) {
				logger.info("[PROGRESS] Downloading: {}%", progress);
			}
		}
	}

	/**
	 * Extracts version and state information from a log line to update internal
	 * cache.
	 * 
	 * @param line The cleaned log line from the device
	 */
	protected void processInternalState(String line) {
		MessageParser.ParsedInfo info = parser.parse(line);
		if (info != null) {
			// If we found aeplFwVer (which returns software="SOFTWARE"), mark it as found
			if ("SOFTWARE".equals(info.software) && line.toLowerCase().contains("aeplfwver")) {
				this.aeplFwVerFound = true;
				this.lastAeplFwVersion = info.version;
				logger.info("[SR] High-fidelity AEPL FW Version found: {}", info.version);
			}

			this.lastSoftwareVersion = info.version;
			if (!info.software.equals("SOFTWARE") && !info.software.equals("FIRMWARE")) {
				this.lastDeviceId = info.software;
			}
			
			// Capture the device state if it's not "LOGIN" or "UNKNOWN"
			if (info.state != null && !info.state.equals("LOGIN") && !info.state.equals("UNKNOWN")) {
				String raw = info.state;
				// if state looks like a two-letter code and we have a resolver, attempt to map
				if (stateResolver != null && raw.matches("^[A-Za-z]{2}$")) {
					try {
						String mapped = stateResolver.resolveStateName(raw);
						if (mapped != null) {
							raw = mapped;
							logger.info("[SR] Mapped state abbreviation '{}' to full name '{}'", info.state, raw);
						}
					} catch (Exception e) {
						logger.warn("[SR] Failed to map state abbreviation {}: {}", raw, e.getMessage());
					}
				}
				this.lastDeviceState = raw;
				logger.debug("[SR] Captured device state: {}", raw);
				// Update the parser with the latest device state for future login packet parsing
				parser.setDeviceState(raw);
			}
			
			if (info.loginPacketInfo != null) {
				this.lastLoginPacketInfo = info.loginPacketInfo;
				// Trigger the creation of a separate serial log file with IMEI
				if (info.loginPacketInfo.imei != null && !info.loginPacketInfo.imei.isEmpty()) {
					logWriter.setImei(info.loginPacketInfo.imei);
				}
			}
			putVersionIntoMap(info.state, info.software, info.version);
		}
	}

	/**
	 * Stores version info in a thread-safe map categorized by device state.
	 * 
	 * @param state    The reported device state
	 * @param software The component name (e.g., APP, GSM)
	 * @param version  The version string
	 */
	private void putVersionIntoMap(String state, String software, String version) {
		stateMap.computeIfAbsent(state, k -> new ConcurrentHashMap<>()).put(software, version);
		logger.debug("[MAP-UPDATE] state={} software={} version={}", state, software, version);
	}

	public BlockingQueue<String> getProcessorQueue() {
		return this.processorQueue;
	}

	public String getVersionFor(String state, String software) {
		ConcurrentMap<String, String> swMap = stateMap.get(state);
		return (swMap == null) ? null : swMap.get(software);
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

	/**
	 * Prepares the reader for a new FOTA cycle by resetting volatile status
	 * variables.
	 */
	public void resetState() {
		this.lastSoftwareVersion = null;
		this.lastAeplFwVersion = null;
		this.lastDownloadProgress = 0.0;
		this.lastDeviceState = null;
		this.lastLoginPacketInfo = null;
		this.aeplFwVerFound = false;
		parser.setDeviceState(null);
		logger.info("[SR] State reset for new cycle.");
	}

	/**
	 * Allows the orchestrator to provide a resolver which can map two-letter
	 * state abbreviations (MH, BR, etc.) to the full state name found in the
	 * servers.json file.  This is used when parsing "statewise" log lines.
	 */
	public void setStateResolver(com.aepl.atcu.logic.FirmwareResolver resolver) {
		this.stateResolver = resolver;
	}

	/**
	 * Sends a raw command down to the serial connection. This can be used by
	 * higher-level orchestrator logic to prompt the device (e.g. ask for a
	 * login packet) without exposing the underlying connection object.
	 *
	 * @param cmd command string, will be suffixed with CRLF when written.
	 */
	public void sendCommand(String cmd) {
		connection.writeEvent(cmd);
	}

	public boolean isAeplFwVerFound() {
		return aeplFwVerFound;
	}

	/**
	 * Loop that monitors standard input for commands to be sent to the device.
	 */
	private void terminalInputLoop() {
		try (Scanner scanner = new Scanner(System.in)) {
			logger.info("[INPUT] Type commands. 'exit' to stop.");
			while (true) {
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
					System.exit(0);
				}
				logger.info("[SEND] {}", cmd);
				connection.writeEvent(cmd);
			}
		} catch (Exception e) {
			logger.error("Error in terminal input loop: {}", e.getMessage(), e);
		}
	}

}
