package com.aepl.atcu.logic;

import java.util.regex.Matcher;
import java.util.regex.Pattern;
import com.aepl.atcu.util.LoginPacketInfo;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Logic class for parsing raw status messages and login packets from device
 * serial output.
 * It uses regular expressions to extract component versions, device states, and
 * download progress.
 * 
 * NOTE: The parser handles multiple formats, including key-value pairs
 * (SOFTWARE: value),
 * binary-mapped login packets (starting with 55AA), and ANSI escape sequence
 * stripping.
 */
public class MessageParser {

	private static final Logger logger = LogManager.getLogger(MessageParser.class);

	private static final Pattern ANSI_ESCAPE = Pattern.compile("\u001B\\[[;\\d]*[A-Za-z]");
	private static final Pattern SOFTWARE_PATTERN = Pattern.compile("(?i)SOFTWARE[:=\\s]+([^\\s,;:\\n#]+)");
	private static final Pattern VERSION_PATTERN = Pattern.compile("(?i)VERSION[:=\\s]+([^\\s,;:\\n]+)");
	private static final Pattern STATE_PATTERN = Pattern.compile("(?i)STATE[:=\\s]+([^\\s,;:\\n]+)");
	private static final Pattern VERSION_SIMPLE = Pattern.compile("\\d+\\.\\d+(?:\\.\\d+)*");
	private static final Pattern FW_VER_PATTERN = Pattern.compile("(?i)aeplFwVer[:=\\s]+([^\\s,;]+)");
	private static final Pattern DOWNLOAD_PATTERN = Pattern.compile("(?i)\\[FOT\\] downloading\\s+([\\d.]+)%");

	/**
	 * Removes ANSI escape codes (colors/formatting) from a string.
	 * 
	 * @param input The raw string from serial
	 * @return Cleaned string without control characters
	 */
	public String stripAnsi(String input) {
		if (input == null)
			return null;
		return ANSI_ESCAPE.matcher(input).replaceAll("");
	}

	/**
	 * Data structure containing parsed device information.
	 */
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

	/**
	 * Parses a single line of text to identify device version or state information.
	 * 
	 * @param line The log line to analyze
	 * @return A ParsedInfo object if data was found, null otherwise
	 */
	public ParsedInfo parse(String line) {
		if (line == null || line.isEmpty())
			return null;

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

	/**
	 * Extracts FOTA download progress percentage from a log line.
	 * 
	 * @param line The device log line
	 * @return Progress as a Double (0-100), or null if not found
	 */
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

	/**
	 * Internal method to parse the comma-separated 55AA login packets.
	 * 
	 * @param line Raw data line
	 * @return ParsedInfo containing a nested LoginPacketInfo
	 */
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
		if (parts.length > 7) {
			String imei = parts.length > 4 ? parts[4].trim() : "";
			String iccid = parts.length > 5 ? parts[5].trim() : "";
			String UIN = parts.length > 6 ? parts[6].trim() : "";
			String foundVersion = parts.length > 7 ? parts[7].trim() : "";
			String vin = parts.length > 8 ? parts[8].trim() : "";

			if (!foundVersion.isEmpty()) {
				// We use null for model and state because they are not present in the login
				// packet.
				// The LoginPacketInfo constructor handles these nulls by setting default
				// values.
				LoginPacketInfo loginInfo = new LoginPacketInfo(imei, iccid, UIN, foundVersion, vin, null, null);
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

	/**
	 * Utility to extract a regex group from a string.
	 * 
	 * @param pattern Compiled pattern with one capture group
	 * @param input   Text to search
	 * @return Trimmed capture group or null
	 */
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
