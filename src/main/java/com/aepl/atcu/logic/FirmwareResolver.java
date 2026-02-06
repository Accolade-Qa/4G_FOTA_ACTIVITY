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

    /**
     * Constructs the resolver with a path to the configuration JSON.
     * 
     * @param jsonPath Path to the servers.json or equivalent mapping file
     */
    public FirmwareResolver(String jsonPath) {
        this.jsonPath = jsonPath;
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
            if (stateName.equalsIgnoreCase(normalizedState)) {
                JsonNode firmwareArray = stateNode.get("firmware");
                if (firmwareArray != null && firmwareArray.isArray()) {
                    List<String> versions = new ArrayList<>();
                    for (JsonNode fw : firmwareArray) {
                        versions.add(fw.get("firmwareVersion").asText().trim());
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
        String s1 = v1.split("_")[0].split("-")[0].trim();
        String s2 = v2.split("_")[0].split("-")[0].trim();
        return s1.equalsIgnoreCase(s2);
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
}
