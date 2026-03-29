package com.aepl.atcu.logic;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class FirmwareResolver {
    private static final Logger logger = LogManager.getLogger(FirmwareResolver.class);
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

    private final String jsonPath;
    private final ObjectMapper mapper = new ObjectMapper();
    private final Map<String, List<String>> versionCache = new HashMap<>();
    private final Map<String, List<FirmwareEntry>> firmwareCache = new HashMap<>();

    public FirmwareResolver(String jsonPath) {
        this.jsonPath = jsonPath;
        loadVersionCache();
    }

    private void loadVersionCache() {
        try {
            File jsonFile = new File(jsonPath);
            if (!jsonFile.exists()) {
                logger.warn("[RESOLVER] Firmware JSON not found at: {}", jsonPath);
                return;
            }

            JsonNode root = mapper.readTree(jsonFile);
            if (!root.isArray()) {
                logger.warn("[RESOLVER] JSON root is not an array");
                return;
            }

            for (JsonNode stateNode : root) {
                String stateName = stateNode.get("state").asText().trim();
                List<String> versions = new ArrayList<>();

                JsonNode firmwareArray = stateNode.get("firmware");
                if (firmwareArray != null && firmwareArray.isArray()) {
                    List<FirmwareEntry> entries = new ArrayList<>();
                    for (JsonNode firmwareNode : firmwareArray) {
                        String fileName = getText(firmwareNode, "fileName");
                        String version = getText(firmwareNode, "firmwareVersion");
                        if (version.isEmpty()) {
                            version = extractVersionFromFileName(fileName);
                        }
                        if (version.isEmpty()) {
                            continue;
                        }
                        entries.add(new FirmwareEntry(version, fileName));
                        if (!versions.contains(version)) {
                            versions.add(version);
                        }
                    }
                    if (!entries.isEmpty()) {
                        firmwareCache.put(stateName, entries);
                    }
                }

                if (versions.isEmpty()) {
                    JsonNode versionsArray = stateNode.get("versions");
                    if (versionsArray != null && versionsArray.isArray()) {
                        for (JsonNode versionNode : versionsArray) {
                            String v = versionNode.asText().trim();
                            if (!v.isEmpty() && !versions.contains(v)) {
                                versions.add(v);
                            }
                        }
                    }
                }

                if (!versions.isEmpty()) {
                    versionCache.put(stateName, versions);
                    logger.info("[RESOLVER] Loaded {} versions for state '{}'", versions.size(), stateName);
                }
            }
            logger.info("[RESOLVER] Cache loaded with {} states", versionCache.size());
        } catch (Exception e) {
            logger.error("[RESOLVER] Error loading version cache: {}", e.getMessage(), e);
        }
    }

    public boolean validateVersionExists(String state, String currentVersion) throws IOException {
        logger.info("[RESOLVER] Validating if version '{}' exists for state: '{}'", currentVersion, state);

        if (state == null || currentVersion == null) {
            logger.warn("[RESOLVER] State or version is null");
            return false;
        }

        List<String> versions = versionCache.get(state);
        if (versions == null) {
            logger.error("[RESOLVER] State '{}' not found in cache", state);
            return false;
        }

        String normalizedCurrent = currentVersion.trim();
        List<FirmwareEntry> entries = firmwareCache.get(state);
        int idx = (entries != null && !entries.isEmpty())
                ? findFirmwareIndex(entries, normalizedCurrent)
                : findVersionIndex(versions, normalizedCurrent);
        boolean exists = (idx >= 0);

        if (exists) {
            logger.info("[RESOLVER] Version '{}' FOUND at index {} in state '{}'", normalizedCurrent, idx, state);
        } else {
            logger.warn("[RESOLVER] Version '{}' NOT FOUND in state '{}'. Available versions: {}",
                    normalizedCurrent, state, versions);
        }

        return exists;
    }

    public String resolveNextVersion(String state, String currentVersion) throws IOException {
        logger.info("[RESOLVER] Resolving next version for State: '{}', Current Version: '{}'", state, currentVersion);

        if (state == null || currentVersion == null) {
            logger.warn("[RESOLVER] State or version is null");
            return null;
        }

        List<String> versions = versionCache.get(state);
        if (versions == null) {
            logger.warn("[RESOLVER] State '{}' not found in cache", state);
            return null;
        }

        String normalizedCurrent = currentVersion.trim();

        List<FirmwareEntry> entries = firmwareCache.get(state);
        if (entries != null && !entries.isEmpty()) {
            int currentIndex = findFirmwareIndex(entries, normalizedCurrent);
            if (currentIndex == -1) {
                logger.warn("[RESOLVER] Current version '{}' not found in firmware list for state '{}'. " +
                        "Available versions: {}", normalizedCurrent, state, versions);
                return null;
            }
            if (currentIndex < entries.size() - 1) {
                String nextVersion = entries.get(currentIndex + 1).version;
                logger.info("[RESOLVER] Current version '{}' found at index {}. Next version: '{}'",
                        normalizedCurrent, currentIndex, nextVersion);
                return nextVersion;
            }
            logger.info("[RESOLVER] Current version '{}' is at last firmware entry for state '{}'.",
                    normalizedCurrent, state);
            return null;
        }

        int currentIndex = findVersionIndex(versions, normalizedCurrent);

        if (currentIndex == -1) {
            logger.warn("[RESOLVER] Current version '{}' not found in version list for state '{}'. " +
                    "Available versions: {}", normalizedCurrent, state, versions);
            return null;
        }

        if (currentIndex < versions.size() - 1) {
            String nextVersion = versions.get(currentIndex + 1);
            logger.info("[RESOLVER] Current version '{}' found at index {}. Next version: '{}'",
                    normalizedCurrent, currentIndex, nextVersion);
            return nextVersion;
        }

        logger.info("[RESOLVER] Current version '{}' is at index {} (last). Device is up-to-date.",
                normalizedCurrent, currentIndex);
        return null;
    }

    public List<String> getVersionsForState(String state) {
        List<String> versions = versionCache.get(state);
        return versions != null ? new ArrayList<>(versions) : new ArrayList<>();
    }

    public List<String> getAllStates() {
        return new ArrayList<>(versionCache.keySet());
    }

    private int findVersionIndex(List<String> versions, String version) {
        if (versions == null || version == null) {
            return -1;
        }
        String normalized = version.trim();
        for (int i = 0; i < versions.size(); i++) {
            if (versions.get(i).equalsIgnoreCase(normalized)) {
                return i;
            }
        }
        return -1;
    }

    private int findFirmwareIndex(List<FirmwareEntry> entries, String version) {
        if (entries == null || version == null) {
            return -1;
        }
        String normalized = version.trim();
        for (int i = 0; i < entries.size(); i++) {
            FirmwareEntry entry = entries.get(i);
            if (entry.version != null && entry.version.equalsIgnoreCase(normalized)) {
                return i;
            }
            if (entry.fileName != null && entry.fileName.toLowerCase().contains(normalized.toLowerCase())) {
                return i;
            }
        }
        return -1;
    }

    private static String getText(JsonNode node, String field) {
        if (node == null || field == null) {
            return "";
        }
        JsonNode value = node.get(field);
        return value == null ? "" : value.asText().trim();
    }

    private static String extractVersionFromFileName(String fileName) {
        if (fileName == null || fileName.isEmpty()) {
            return "";
        }
        var matcher = VERSION_PATTERN.matcher(fileName);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return "";
    }
}