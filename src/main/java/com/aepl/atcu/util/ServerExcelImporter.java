package com.aepl.atcu.util;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

public class ServerExcelImporter {

    private static final Logger logger = LogManager.getLogger(ServerExcelImporter.class);
    private static final java.util.regex.Pattern VERSION_PATTERN =
            java.util.regex.Pattern.compile("(\\d+(?:\\.\\d+)+)");

    private static final class FirmwareEntry {
        private final String version;
        private final String fileName;

        private FirmwareEntry(String version, String fileName) {
            this.version = version;
            this.fileName = fileName;
        }
    }
    public static boolean updateServersJsonFromExcel(Path inputDir, Path outputJsonPath, String targetSheetName) {
        try {
            Path excelPath = findExcelFile(inputDir);
            if (excelPath == null) {
                logger.info("[EXCEL] No Excel file found in {}", inputDir);
                return false;
            }

            Map<String, List<FirmwareEntry>> stateFirmware = parseExcel(excelPath, targetSheetName);
            if (stateFirmware.isEmpty()) {
                logger.warn("[EXCEL] No valid server/firmware rows found in {}", excelPath);
                return false;
            }

            writeServersJson(outputJsonPath, stateFirmware);
            logger.info("[EXCEL] Updated servers.json from {}", excelPath);
            return true;
        } catch (Exception e) {
            logger.error("[EXCEL] Failed to update servers.json: {}", e.getMessage(), e);
            return false;
        }
    }

    private static Path findExcelFile(Path inputDir) throws IOException {
        if (inputDir == null || !Files.exists(inputDir)) {
            return null;
        }
        List<Path> excelFiles = new ArrayList<>();
        try (var stream = Files.list(inputDir)) {
            stream.filter(p -> {
                String name = p.getFileName().toString().toLowerCase(Locale.ROOT);
                return name.endsWith(".xlsx") || name.endsWith(".xls");
            }).forEach(excelFiles::add);
        }
        if (excelFiles.isEmpty()) {
            return null;
        }
        excelFiles.sort(Comparator.comparing(p -> p.getFileName().toString().toLowerCase(Locale.ROOT)));

        for (Path p : excelFiles) {
            String name = p.getFileName().toString().toLowerCase(Locale.ROOT);
            if (name.equals("server_inputs.xlsx")) {
                return p;
            }
            if (name.contains("government")) {
                return p;
            }
        }
        return excelFiles.get(0);
    }

    private static Map<String, List<FirmwareEntry>> parseExcel(Path excelPath, String targetSheetName) throws Exception {
        Map<String, List<FirmwareEntry>> result = new LinkedHashMap<>();
        DataFormatter formatter = new DataFormatter();

        try (InputStream in = Files.newInputStream(excelPath);
             Workbook wb = WorkbookFactory.create(in)) {

            if (targetSheetName != null && !targetSheetName.trim().isEmpty()) {
                Sheet target = wb.getSheet(targetSheetName);
                if (target == null) {
                    logger.warn("[EXCEL] Sheet '{}' not found in {}", targetSheetName, excelPath.getFileName());
                    return result;
                }
            }

            for (int s = 0; s < wb.getNumberOfSheets(); s++) {
                Sheet sheet = wb.getSheetAt(s);
                if (sheet == null) {
                    continue;
                }
                String sheetName = sheet.getSheetName();
                if (sheetName == null || sheetName.trim().isEmpty()) {
                    continue;
                }
                if ("summary".equalsIgnoreCase(sheetName.trim())) {
                    continue;
                }

                int firstRow = sheet.getFirstRowNum();
                Row headerRow = sheet.getRow(firstRow);
                int lastCell = headerRow != null ? headerRow.getLastCellNum() : -1;

                int fwCol = -1;
                int fileCol = -1;

                if (headerRow != null && lastCell > 0) {
                    for (int c = 0; c < lastCell; c++) {
                        String header = normalize(formatter.formatCellValue(headerRow.getCell(c)));
                        if (header.isEmpty()) {
                            continue;
                        }
                        if (header.contains("firmwarename") || header.equals("firmware") || header.equals("version")) {
                            fwCol = c;
                        } else if (header.contains("firmwarefilename") || header.equals("filename")
                                || header.contains("firmwarefile")) {
                            fileCol = c;
                        }
                    }
                }

                boolean headerLooksValid = fwCol != -1;
                int dataStartRow = headerLooksValid ? firstRow + 1 : firstRow;

                if (fwCol == -1) {
                    fwCol = 1; // default to second column for "Firmware Name"
                }

                List<FirmwareEntry> entries = new ArrayList<>();
                for (int r = dataStartRow; r <= sheet.getLastRowNum(); r++) {
                    Row row = sheet.getRow(r);
                    if (row == null) {
                        continue;
                    }

                    String fwName = formatCell(formatter, row.getCell(fwCol));
                    String fileName = fileCol >= 0 ? formatCell(formatter, row.getCell(fileCol)) : "";
                    if (fwName.isEmpty() && (fileName == null || fileName.isEmpty())) {
                        continue;
                    }
                    String version = extractVersionFromCells(fwName, fileName);
                    if (version.isEmpty()) {
                        continue;
                    }
                    entries.add(new FirmwareEntry(version, fileName));
                }
                if (!entries.isEmpty()) {
                    result.put(sheetName, entries);
                }
            }
        }

        return result;
    }

    private static void writeServersJson(Path outputJsonPath, Map<String, List<FirmwareEntry>> stateFirmware)
            throws IOException {
        ObjectMapper mapper = new ObjectMapper();
        ArrayNode root = mapper.createArrayNode();
        for (Map.Entry<String, List<FirmwareEntry>> entry : stateFirmware.entrySet()) {
            ObjectNode node = mapper.createObjectNode();
            node.put("state", entry.getKey());
            ArrayNode versions = node.putArray("versions");
            ArrayNode firmware = node.putArray("firmware");
            List<String> uniqueVersions = new ArrayList<>();
            for (FirmwareEntry fw : entry.getValue()) {
                if (!uniqueVersions.contains(fw.version)) {
                    uniqueVersions.add(fw.version);
                    versions.add(fw.version);
                }
                if (fw.fileName != null && !fw.fileName.isEmpty()) {
                    ObjectNode fwNode = mapper.createObjectNode();
                    fwNode.put("firmwareVersion", fw.version);
                    fwNode.put("fileName", fw.fileName);
                    firmware.add(fwNode);
                }
            }
            root.add(node);
        }
        mapper.writerWithDefaultPrettyPrinter().writeValue(outputJsonPath.toFile(), root);
    }

    private static String normalize(String s) {
        if (s == null) {
            return "";
        }
        return s.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }

    private static String formatCell(DataFormatter formatter, Cell cell) {
        if (cell == null) {
            return "";
        }
        String raw = formatter.formatCellValue(cell);
        return raw == null ? "" : raw.trim();
    }

    private static String extractVersionFromCells(String firmwareName, String fileName) {
        String fromName = extractVersionFromText(firmwareName);
        if (!fromName.isEmpty()) {
            return fromName;
        }
        String fromFile = extractVersionFromText(fileName);
        if (!fromFile.isEmpty()) {
            return fromFile;
        }
        return firmwareName == null ? "" : firmwareName.trim();
    }

    private static String extractVersionFromText(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        var matcher = VERSION_PATTERN.matcher(text);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return "";
    }

}


