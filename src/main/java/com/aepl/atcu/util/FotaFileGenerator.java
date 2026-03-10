package com.aepl.atcu.util;

import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.Reader;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVPrinter;
import org.apache.commons.csv.CSVRecord;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class FotaFileGenerator {

	private static final Logger logger = LogManager.getLogger(FotaFileGenerator.class);


	public static String generateBatchFile(String sourceCsvPath, String outputCsvPath) throws IOException {
		logger.info("[GEN] Reading source CSV: {}", sourceCsvPath);

		Reader in = new FileReader(sourceCsvPath);
		CSVParser parser = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build().parse(in);

		List<String> headers = parser.getHeaderNames();
		List<List<String>> newRecords = new ArrayList<>();

		for (CSVRecord record : parser) {
			String uin = record.isMapped("UIN") ? record.get("UIN") : "Unknown";
			
			// Validate UIN starts with ACON
			if (!ValidationUtils.isValidUin(uin)) {
				logger.warn("[GEN] Skipping record with invalid UIN (must start with {}): {}", "ACON", uin);
				continue;
			}
			
			String oldUfw = record.get("UFW");
			String newUfw = incrementUfw(oldUfw);

			logger.debug("[GEN] {}: {} -> {}", uin, oldUfw, newUfw);

			List<String> row = new ArrayList<>();
			for (String header : headers) {
				if (header.equalsIgnoreCase("UFW")) {
					row.add(newUfw);
				} else {
					row.add(record.get(header));
				}
			}
			newRecords.add(row);
		}
		in.close();

		logger.info("[GEN] Writing to: {}", outputCsvPath);
		FileWriter out = new FileWriter(outputCsvPath);
		CSVPrinter printer = new CSVPrinter(out,
				CSVFormat.DEFAULT.builder().setHeader(headers.toArray(new String[0])).build());

		for (List<String> row : newRecords) {
			printer.printRecord(row);
		}

		printer.close();
		return Paths.get(outputCsvPath).toAbsolutePath().toString();
	}


	public static String generateBatchFileWithExplicitVersion(String sourceCsvPath, String outputCsvPath,
			String targetVersion) throws IOException {
		logger.info("[GEN] Reading source CSV: {} using target version: {}", sourceCsvPath, targetVersion);

		Reader in = new FileReader(sourceCsvPath);
		CSVParser parser = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build().parse(in);

		List<String> headers = parser.getHeaderNames();
		List<List<String>> newRecords = new ArrayList<>();

		for (CSVRecord record : parser) {
			String uin = record.isMapped("UIN") ? record.get("UIN") : "Unknown";
			
			// Validate UIN starts with ACON
			if (!ValidationUtils.isValidUin(uin)) {
				logger.warn("[GEN] Skipping record with invalid UIN (must start with {}): {}", "ACON", uin);
				continue;
			}
			
			List<String> row = new ArrayList<>();
			for (String header : headers) {
				if (header.equalsIgnoreCase("UFW")) {
					row.add(targetVersion);
				} else {
					row.add(record.get(header));
				}
			}
			newRecords.add(row);
		}
		in.close();

		FileWriter out = new FileWriter(outputCsvPath);
		CSVPrinter printer = new CSVPrinter(out,
				CSVFormat.DEFAULT.builder().setHeader(headers.toArray(new String[0])).build());
		for (List<String> row : newRecords) {
			printer.printRecord(row);
		}
		printer.close();

		return Paths.get(outputCsvPath).toAbsolutePath().toString();
	}


	public static String writeLoginPacketInfoCsv(List<LoginPacketInfo> infos, String outputCsvPath) throws IOException {
		String[] headers = { "UIN", "UFW", "MODEL", "IMEI" };
		FileWriter out = new FileWriter(outputCsvPath);
		CSVPrinter printer = new CSVPrinter(out, CSVFormat.DEFAULT.builder().setHeader(headers).build());
		for (LoginPacketInfo info : infos) {
			printer.printRecord((Object[]) info.toCsvRow());
		}
		printer.close();
		return Paths.get(outputCsvPath).toAbsolutePath().toString();
	}


	public static String incrementUfw(String ufw) {
		if (ufw == null || ufw.isEmpty())
			return ufw;

		Pattern p = Pattern.compile("(.*?)(\\d+)$");
		Matcher m = p.matcher(ufw);
		if (m.find()) {
			String prefix = m.group(1);
			String numberStr = m.group(2);
			long num = Long.parseLong(numberStr);
			num++;
			String newNumberStr = String.format("%0" + numberStr.length() + "d", num);
			return prefix + newNumberStr;
		}
		return ufw + "_1";
	}

	public static void writeAuditReport(String auditCsvPath, String uin, String prevVer, String nextVer, String status,
			String error) throws IOException {
		String[] headers = { "Timestamp", "UIN", "Previous_Version", "Target_Version", "Status", "Details" };
		boolean exists = java.nio.file.Files.exists(Paths.get(auditCsvPath));

		FileWriter out = new FileWriter(auditCsvPath, true);
		CSVPrinter printer;
		if (!exists) {
			printer = new CSVPrinter(out, CSVFormat.DEFAULT.builder().setHeader(headers).build());
		} else {
			printer = new CSVPrinter(out, CSVFormat.DEFAULT);
		}

		String timestamp = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new java.util.Date());
		printer.printRecord(timestamp, uin, prevVer, nextVer, status, error);
		printer.close();
	}
}
