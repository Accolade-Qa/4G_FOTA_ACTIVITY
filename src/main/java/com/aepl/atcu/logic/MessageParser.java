package com.aepl.atcu.logic;

import java.util.regex.Matcher;
import java.util.regex.Pattern;
import com.aepl.atcu.Launcher;
import com.aepl.atcu.util.LoginPacketInfo;
import com.aepl.atcu.util.ValidationUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class MessageParser {

	private static final Logger logger = LogManager.getLogger(MessageParser.class);

	private static final Pattern ANSI_ESCAPE = Pattern.compile("\u001B\\[[;\\d]*[A-Za-z]");
	private static final Pattern SOFTWARE_PATTERN = Pattern.compile("(?i)SOFTWARE[:=\\s]+([^\\s,;:\\n#]+)");
	private static final Pattern VERSION_PATTERN = Pattern.compile("(?i)VERSION[:=\\s]+([^\\s,;:\\n]+)");
	private static final Pattern STATE_PATTERN = Pattern.compile("(?i)STATE[:=\\s]+([^\\s,;:\\n]+)");
	private static final Pattern VERSION_SIMPLE = Pattern.compile("\\d+\\.\\d+(?:\\.\\d+)*");
	private static final Pattern FW_VER_PATTERN = Pattern.compile("(?i)aeplFwVer[:=\\s]+([^\\s,;]+)");
	private static final Pattern DOWNLOAD_PATTERN = Pattern.compile("(?i)\\[FOT\\].*?downloading\\s+([\\d.]+)%");
	private static final Pattern VERSION_PREFIX = Pattern.compile("^(\\d+\\.\\d+(?:\\.\\d+)*)");

	public String stripAnsi(String input) {
		if (input == null)
			return null;
		return ANSI_ESCAPE.matcher(input).replaceAll("");
	}

	public static class ParsedInfo {
		public final String state;
		public final String software;
		public final String version;
		public LoginPacketInfo loginPacketInfo;

		public ParsedInfo(String state, String software, String version) {
			this.state = state;
			this.software = software;
			this.version = version;
		}

		public ParsedInfo(String state, String software, String version, LoginPacketInfo loginPacketInfo) {
			this.state = state;
			this.software = software;
			this.version = version;
			this.loginPacketInfo = loginPacketInfo;
		}
	}

	public ParsedInfo parse(String line) {
		if (line == null || line.isEmpty())
			return null;

		if (line.toLowerCase().contains("statewise")) {
			// capture the last two-letter uppercase abbreviation, e.g. "MH" in the line
			Matcher m = Pattern.compile("\\b([A-Z]{2})\\b").matcher(line);
			String candidate = null;
			while (m.find()) {
				candidate = m.group(1);
			}
			if (candidate != null) {
				logger.debug("[PARSER] Detected statewise abbreviation: {}", candidate);
				return new ParsedInfo(candidate.trim(), "STATEWISE", null);
			}
		}

		String software = extractToken(SOFTWARE_PATTERN, line);
		String version = extractToken(VERSION_PATTERN, line);
		String state = extractToken(STATE_PATTERN, line);

		if (software != null && version != null && state != null) {
			return new ParsedInfo(state.trim(), software.trim(), version.trim());
		}

		String fwVer = extractToken(FW_VER_PATTERN, line);
		if (fwVer != null) {
			logger.info("[PARSER] Found aeplFwVer: {}", fwVer);
			return new ParsedInfo("STABLE", "SOFTWARE", fwVer.trim());
		}

		if (software != null && version == null) {
			if (VERSION_SIMPLE.matcher(software).find()) {
				return new ParsedInfo(state == null ? "UNKNOWN" : state.trim(), "SOFTWARE", software.trim());
			}
		}

		if (line.startsWith("55AA") || line.contains("55AA,")) {
			logger.debug("[PARSER] Attempting to parse login packet for line: {}", line);
			return parseLoginPacket(line);
		}

		Matcher mVer = VERSION_SIMPLE.matcher(line);
		if (mVer.find()) {
			String v = mVer.group();
			logger.debug("[PARSER] Found standalone version suffix-like: {}", v);
			return new ParsedInfo("UNKNOWN", "SOFTWARE", v);
		}

		logger.trace("[PARSER] No match for line: {}", line);
		return null;
	}

	public Double parseDownloadProgress(String line) {
		if (line == null)
			return null;
		Matcher m = DOWNLOAD_PATTERN.matcher(line);
		if (m.find()) {
			try {
				return Double.parseDouble(m.group(1));
			} catch (Exception e) {
				return null;
			}
		}
		return null;
	}
	private ParsedInfo parseLoginPacket(String line) {
		String payload = line;
		if (payload.contains("|")) {
			int startPipe = payload.indexOf('|');
			int endPipe = payload.lastIndexOf('|');
			if (startPipe != endPipe) {
				payload = payload.substring(startPipe + 1, endPipe);
			} else if (startPipe != -1) {
				payload = payload.substring(startPipe + 1);
			}
		}

		String[] parts = payload.split(",");
		if (parts.length > 2) {
			String typeFlag = parts[2].trim();
			if (!"2".equals(typeFlag)) {
				logger.debug("[PARSER] Non-login packet detected (type flag {}), skipping.", typeFlag);
				return null;
			}
			// if 1 in login packet, then it is a health packet
			if ("1".equals(typeFlag)) {
				logger.debug("[PARSER] Health packet detected (type flag 1), skipping.");
				return null;
			}
		}
		if (parts.length > 7) {
			String imei = parts.length > 4 ? parts[4].trim() : "";
			String iccid = parts.length > 5 ? parts[5].trim() : "";
			String UIN = parts.length > 6 ? parts[6].trim() : "";
			String foundVersionRaw = parts.length > 7 ? parts[7].trim() : "";
			String foundVersion = normalizeVersion(foundVersionRaw);
			String vin = parts.length > 8 ? parts[8].trim() : "";

			if (!ValidationUtils.isValidUin(UIN)) {
				logger.warn("[PARSER] Invalid UIN (must start with {}): {}. Skipping login packet.",
						"ACON", UIN);
				return null;
			}

			if (!ValidationUtils.isValidImei(imei)) {
				logger.warn("[PARSER] Invalid IMEI (must be 13-15 digits): {}. Skipping login packet.",
						imei);
				return null;
			}

			if (foundVersion != null && !foundVersion.isEmpty()) {
				String stateForPacket = (Launcher.getCurrentState() != null && !Launcher.getCurrentState().isEmpty())
						? Launcher.getCurrentState()
						: null;
				LoginPacketInfo loginInfo = new LoginPacketInfo(imei, iccid, UIN, foundVersion, vin, null,
						stateForPacket);
				logger.info("[PARSER] Valid login packet: UIN={}, IMEI={}, Version={}, State={}", UIN, imei,
						foundVersion, stateForPacket);
				return new ParsedInfo("LOGIN", UIN, foundVersion, loginInfo);
			}
		}

		for (String p : parts) {
			String t = p.trim();
			if (VERSION_SIMPLE.matcher(t).matches()) {
				return new ParsedInfo("LOGIN", "UNKNOWN", t);
			}
		}
		return null;
	}

	private static String normalizeVersion(String raw) {
		if (raw == null) {
			return null;
		}
		String trimmed = raw.trim();
		Matcher m = VERSION_PREFIX.matcher(trimmed);
		if (m.find()) {
			return m.group(1);
		}
		return trimmed;
	}

	private static String extractToken(Pattern pattern, String input) {
		if (input == null)
			return null;
		Matcher m = pattern.matcher(input);
		if (m.find()) {
			String g = m.group(1);
			return (g != null) ? g.trim() : null;
		}
		return null;
	}
}
