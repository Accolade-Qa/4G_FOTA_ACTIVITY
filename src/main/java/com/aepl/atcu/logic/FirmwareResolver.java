package com.aepl.atcu.logic;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Logic class for determining the next firmware version for a device.
 * It reads a JSON mapping file that defines firmware sequences for different
 * states.
 * 
 * NOTE: The resolver supports both explicit sequence matching (matching the
 * exact version in the list
 * and taking the next) and numerical fallback (finding the first version
 * GREATER than the current).
 */
public class FirmwareResolver {

    private static final Logger logger = LogManager.getLogger(FirmwareResolver.class);
    private final String jsonPath;
    private final ObjectMapper mapper = new ObjectMapper();
    // cache abbreviation -> stateName map, lazily populated
    private java.util.Map<String,String> abbreviationMap = null;

    /**
     * Constructs the resolver with a path to the configuration JSON.
     * 
     * @param jsonPath Path to the servers.json or equivalent mapping file
     */
    public FirmwareResolver(String jsonPath) {
        this.jsonPath = jsonPath;
    }

    /**
     * Validates whether the current version exists in the servers.json
     * configuration for the given state. This ensures the device's reported
     * version is a known/valid version before proceeding with FOTA batch.
     * 
     * @param state          The device's state
     * @param currentVersion The version currently on the device
     * @return True if the version exists in the state's firmware list, false otherwise
     * @throws IOException If the JSON mapping file is missing or unreadable
     */
    public boolean validateVersionExists(String state, String currentVersion) throws IOException {
        logger.info("[RESOLVER] Validating if version '{}' exists in JSON for state: '{}'", currentVersion, state);
        File jsonFile = new File(jsonPath);
        if (!jsonFile.exists()) {
            logger.error("[RESOLVER] Firmware JSON not found at: {}", jsonPath);
            throw new IOException("Firmware JSON not found at: " + jsonPath);
        }

        JsonNode root = mapper.readTree(jsonFile);
        if (!root.isArray()) {
            logger.error("[RESOLVER] JSON root is not an array");
            return false;
        }

        String normalizedState = (state == null) ? "" : state.trim();
        String normalizedCurrent = (currentVersion == null) ? "" : currentVersion.trim();

        for (JsonNode stateNode : root) {
            String stateName = stateNode.get("state").asText().trim();
            if (stateName.equalsIgnoreCase(normalizedState)) {
                JsonNode firmwareArray = stateNode.get("firmware");
                if (firmwareArray != null && firmwareArray.isArray()) {
                    for (JsonNode fw : firmwareArray) {
                        String filename = fw.get("fileName").asText().trim();
                        String binaryVersion = extractVersionFromFilename(filename);
                        if (isSameVersion(binaryVersion, normalizedCurrent)) {
                            logger.info("[RESOLVER] Version '{}' FOUND in JSON for state '{}'", normalizedCurrent, stateName);
                            return true;
                        }
                    }
                    logger.warn("[RESOLVER] Version '{}' NOT FOUND in JSON for state '{}'. Available versions: {}",
                            normalizedCurrent, stateName, getVersionsForState(stateNode));
                    return false;
                }
            }
        }

        logger.warn("[RESOLVER] State '{}' not found in JSON", normalizedState);
        return false;
    }

    /**
     * Helper method to extract and log available versions for a state node.
     */
    private List<String> getVersionsForState(JsonNode stateNode) {
        List<String> versions = new ArrayList<>();
        JsonNode firmwareArray = stateNode.get("firmware");
        if (firmwareArray != null && firmwareArray.isArray()) {
            for (JsonNode fw : firmwareArray) {
                String filename = fw.get("fileName").asText().trim();
                String binaryVersion = extractVersionFromFilename(filename);
                versions.add(binaryVersion);
            }
        }
        return versions;
    }

    /**
     * Resolves the next target version based on state and current version.
     * 
     * @param state          The reported state of the device
     * @param currentVersion The version currently installed on the device
     * @return The next version string to upgrade to, or null if no upgrade is
     *         needed
     * @throws IOException If the JSON mapping file is missing or unreadable
     */
    public String resolveNextVersion(String state, String currentVersion) throws IOException {
        logger.info("[RESOLVER] Resolving next version for State: '{}', Current Version: '{}'", state, currentVersion);
        File jsonFile = new File(jsonPath);
        if (!jsonFile.exists()) {
            logger.error("[RESOLVER] Firmware JSON not found at: {}", jsonPath);
            throw new IOException("Firmware JSON not found at: " + jsonPath);
        }

        JsonNode root = mapper.readTree(jsonFile);
        if (!root.isArray()) {
            logger.error("[RESOLVER] JSON root is not an array");
            return null;
        }

        String normalizedState = (state == null) ? "" : state.trim();
        String normalizedCurrent = (currentVersion == null) ? "" : currentVersion.trim();

        for (JsonNode stateNode : root) {
            String stateName = stateNode.get("state").asText().trim();
            // populate abbreviation map while we're scanning
            if (abbreviationMap == null) {
                abbreviationMap = new java.util.HashMap<>();
            }
            JsonNode abbrNode = stateNode.get("stateAbbreviation");
            if (abbrNode != null && !abbrNode.asText().isEmpty()) {
                abbreviationMap.put(abbrNode.asText().trim().toUpperCase(), stateName);
            }
            if (stateName.equalsIgnoreCase(normalizedState)) {
                JsonNode firmwareArray = stateNode.get("firmware");
                if (firmwareArray != null && firmwareArray.isArray()) {
                    List<String> versions = new ArrayList<>();
                    List<String> filenames = new ArrayList<>();
                    for (JsonNode fw : firmwareArray) {
                        String filename = fw.get("fileName").asText().trim();
                        filenames.add(filename);
                        // Extract binary version from filename (e.g., ATCU_5.2.8_REL24.bin -> 5.2.8_REL24)
                        String binaryVersion = extractVersionFromFilename(filename);
                        versions.add(binaryVersion);
                        logger.debug("[RESOLVER] File: {}, Binary Version: {}", filename, binaryVersion);
                    }

                    logger.debug("[RESOLVER] Found versions in JSON for {}: {}", stateName, versions);

                    int currentIndex = -1;
                    for (int i = 0; i < versions.size(); i++) {
                        if (isSameVersion(versions.get(i), normalizedCurrent)) {
                            currentIndex = i;
                            break;
                        }
                    }

                    if (currentIndex != -1) {
                        if (currentIndex < versions.size() - 1) {
                            String next = versions.get(currentIndex + 1);
                            logger.info(
                                    "[RESOLVER] Current version '{}' matched JSON at index {}. Selecting next in sequence: '{}'",
                                    normalizedCurrent, currentIndex, next);
                            return next;
                        } else {
                            logger.info(
                                    "[RESOLVER] Current version '{}' matched last entry in JSON sequence. Up-to-date.",
                                    normalizedCurrent);
                            return null;
                        }
                    } else {
                        logger.info(
                                "[RESOLVER] Current version '{}' not found in JSON list. Searching for next higher version...",
                                normalizedCurrent);
                        for (String v : versions) {
                            if (compareVersions(v, normalizedCurrent) > 0) {
                                logger.info("[RESOLVER] Found next updated version numerically: '{}' > '{}'", v,
                                        normalizedCurrent);
                                return v;
                            }
                        }

                        if (!versions.isEmpty() && compareVersions(versions.get(0), normalizedCurrent) > 0) {
                            return versions.get(0);
                        }

                        logger.info(
                                "[RESOLVER] No newer version found in JSON for {}. Device might be newer than all definitions.",
                                normalizedState);
                        return null;
                    }
                }
            }
        }

        logger.warn("[RESOLVER] No mapping found for state: '{}'", normalizedState);
        return null;
    }

    /**
     * Compares two version strings considering only the major components.
     * 
     * @param v1 First version string
     * @param v2 Second version string
     * @return True if the major version components match (ignoring suffixes like
     *         _REL)
     */
    private boolean isSameVersion(String v1, String v2) {
        if (v1 == null || v2 == null)
            return false;
        // Remove all non-numeric and non-dot characters to compare base versions
        // e.g., 5.2.8_REL24 -> 5.2.8 and 5.2.8_REL24 -> 5.2.8 (exact match)
        String s1 = v1.split("_")[0].split("-")[0].trim();
        String s2 = v2.split("_")[0].split("-")[0].trim();
        return s1.equalsIgnoreCase(s2);
    }

    /**
     * Extracts the firmware version from a binary filename.
     * Pattern: ATCU_5.2.8_REL24.bin -> 5.2.8_REL24
     * 
     * @param filename The binary filename
     * @return Extracted version string, or the original filename if extraction fails
     */
    private String extractVersionFromFilename(String filename) {
        if (filename == null || filename.isEmpty()) {
            return "";
        }
        
        // Remove directory path if present
        String name = filename.substring(filename.lastIndexOf(java.io.File.separator) + 1);
        
        // Pattern: ATCU_X.X.X_RELMM.bin or similar
        // Remove extension
        if (name.endsWith(".bin")) {
            name = name.substring(0, name.length() - 4);
        }
        
        // Remove prefix (ATCU_)
        if (name.startsWith("ATCU_") || name.startsWith("atcu_")) {
            name = name.substring(5);
        }
        
        // Remove trailing " - Copy" or similar variations
        if (name.contains(" - ")) {
            name = name.substring(0, name.indexOf(" - ")).trim();
        }
        
        logger.debug("[RESOLVER] Extracted version from filename '{}': '{}'", filename, name);
        return name;
    }


    /**
     * Numerically compares two semantic-like version strings.
     * 
     * @param v1 Version 1
     * @param v2 Version 2
     * @return Positive value if v1 > v2, negative if v1 < v2, 0 if equal.
     */
    private int compareVersions(String v1, String v2) {
        try {
            String s1 = v1.replaceAll("[^0-9.]", "");
            String s2 = v2.replaceAll("[^0-9.]", "");

            if (s1.isEmpty() || s2.isEmpty())
                return v1.compareToIgnoreCase(v2);

            String[] p1 = s1.split("\\.");
            String[] p2 = s2.split("\\.");

            int length = Math.max(p1.length, p2.length);
            for (int i = 0; i < length; i++) {
                int num1 = i < p1.length && !p1[i].isEmpty() ? Integer.parseInt(p1[i]) : 0;
                int num2 = i < p2.length && !p2[i].isEmpty() ? Integer.parseInt(p2[i]) : 0;
                if (num1 < num2)
                    return -1;
                if (num1 > num2)
                    return 1;
            }
            return 0;
        } catch (Exception e) {
            return v1.compareToIgnoreCase(v2);
        }
    }

    /**
     * Resolve a full state name for a given two‑letter abbreviation.
     * Reads the JSON mapping file if necessary and caches the results.
     *
     * @param abbr Two‑letter state abbreviation (e.g. "MH", "BR")
     * @return The corresponding state name from servers.json or null if not found
     * @throws IOException If the JSON cannot be loaded
     */
    public String resolveStateName(String abbr) throws IOException {
        if (abbr == null)
            return null;
        if (abbreviationMap == null) {
            // force a read of the file to build the map
            initAbbreviationMap();
        }
        return abbreviationMap.get(abbr.trim().toUpperCase());
    }

    /**
     * Reads the JSON configuration and builds the abbreviation map.
     */
    private void initAbbreviationMap() throws IOException {
        abbreviationMap = new java.util.HashMap<>();
        File jsonFile = new File(jsonPath);
        if (!jsonFile.exists()) {
            throw new IOException("Firmware JSON not found at: " + jsonPath);
        }
        JsonNode root = mapper.readTree(jsonFile);
        if (root.isArray()) {
            for (JsonNode stateNode : root) {
                JsonNode abbrNode = stateNode.get("stateAbbreviation");
                JsonNode nameNode = stateNode.get("state");
                if (abbrNode != null && nameNode != null) {
                    String a = abbrNode.asText().trim().toUpperCase();
                    String n = nameNode.asText().trim();
                    if (!a.isEmpty() && !n.isEmpty()) {
                        abbreviationMap.put(a, n);
                    }
                }
            }
        }
    }
}
