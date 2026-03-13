package com.aepl.atcu;

import java.io.FileInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Properties;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import com.aepl.atcu.util.ServerExcelImporter;

public class Launcher {
	private static final Logger logger = LogManager.getLogger(Launcher.class);
	private static String currentState = null;
	private static String defaultState = null;
	private static final String DEFAULT_STATE = "DO NOT DELETE";
	private static final String SERIAL_PORT_DEFAULT = "";
	private static final int BAUD_RATE_DEFAULT = 115200;
	private static final String FIRMWARE_JSON_DEFAULT = "input/servers.json";
	private static final String AUDIT_CSV_DEFAULT = "results/fota_audit.csv";
	private static final String LOGIN_JSON_DEFAULT = "results/login_packets.json";
	private static final String PORTAL_URL_DEFAULT = "http://aepl-tcu4g-qa.accoladeelectronics.com:6102/login";
	private static final String PORTAL_USER_DEFAULT = "suraj.bhalerao@accoladeelectronics.com";
	private static final String PORTAL_PASS_DEFAULT = "79hqelye";

	public static String getDefaultState() {
		return defaultState == null ? DEFAULT_STATE : defaultState;
	}

	public static String getCurrentState() {
		return currentState;
	}

	public static void setCurrentState(String state) {
		currentState = state;
	}

	public static void main(String[] args) {
		setupDirectories();

		try {
			Properties props = loadConfig();
			defaultState = getProp(props, "state", DEFAULT_STATE);
			String serialPort = getProp(props, "serial.port", SERIAL_PORT_DEFAULT);
			int baudRate = getIntProp(props, "serial.baud", BAUD_RATE_DEFAULT);
			String firmwareJson = getProp(props, "firmware.json", FIRMWARE_JSON_DEFAULT);
			String auditCsv = getProp(props, "audit.csv", AUDIT_CSV_DEFAULT);
			String loginJson = getProp(props, "login.json", LOGIN_JSON_DEFAULT);
			String portalUrl = getProp(props, "login.url", PORTAL_URL_DEFAULT);
			String portalUser = getProp(props, "login.user", PORTAL_USER_DEFAULT);
			String portalPass = getProp(props, "login.pass", PORTAL_PASS_DEFAULT);

			logger.info("===== FOTA AUTOMATION LAUNCHER =====");
			logger.info("Serial Port: {}",
					(serialPort == null || serialPort.trim().isEmpty()) ? "AUTO-DETECT" : serialPort);
			logger.info("Baud Rate: {}", baudRate);
			logger.info("Firmware JSON: {}", firmwareJson);
			logger.info("Audit CSV: {}", auditCsv);
			logger.info("Login JSON: {}", loginJson);
			logger.info("Portal URL: {}", portalUrl);
			logger.info("Default State: {}", defaultState);

			Orchestrator orch = new Orchestrator(serialPort, baudRate, auditCsv, firmwareJson, loginJson);
			orch.start(portalUrl, portalUser, portalPass);
		} catch (Exception e) {
			logger.fatal("Fatal error starting orchestrator: {}", e.getMessage(), e);
			System.err.println("FATAL: " + e.getMessage());
			e.printStackTrace();
			System.exit(1);
		}
	}

	private static void setupDirectories() {
		String[] dirs = { "input", "output", "logs", "results", "screenshots" };
		for (String dir : dirs) {
			Path path = Paths.get(dir);
			if (Files.notExists(path)) {
				try {
					Files.createDirectory(path);
					logger.info("Created directory: {}", dir);
				} catch (Exception e) {
					logger.warn("Failed to create directory {}: {}", dir, e.getMessage());
				}
			}
		}
	}

	private static Properties loadConfig() {
		Properties props = new Properties();
		String configPath = System.getProperty("fota.config", "config.properties");
		Path path = Paths.get(configPath);
		if (!Files.exists(path)) {
			logger.warn("Config file not found at {}. Using defaults.", path.toAbsolutePath());
			return props;
		}
		try (FileInputStream in = new FileInputStream(path.toFile())) {
			props.load(in);
			logger.info("Loaded config from {}", path.toAbsolutePath());
		} catch (Exception e) {
			logger.warn("Failed to load config at {}: {}", path.toAbsolutePath(), e.getMessage());
		}
		return props;
	}

	private static String getProp(Properties props, String key, String fallback) {
		if (props == null || key == null) {
			return fallback;
		}
		String value = props.getProperty(key);
		return (value == null || value.trim().isEmpty()) ? fallback : value.trim();
	}

	private static int getIntProp(Properties props, String key, int fallback) {
		String value = getProp(props, key, String.valueOf(fallback));
		try {
			return Integer.parseInt(value.trim());
		} catch (NumberFormatException e) {
			logger.warn("Invalid integer for {}='{}'; using {}", key, value, fallback);
			return fallback;
		}
	}
}
