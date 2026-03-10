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
    private final String jsonPath;
    private final ObjectMapper mapper = new ObjectMapper();
    private final Map<String, List<String>> versionCache = new HashMap<>();

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
                JsonNode versionsArray = stateNode.get("versions");
                
                if (versionsArray != null && versionsArray.isArray()) {
                    List<String> versions = new ArrayList<>();
                    for (JsonNode versionNode : versionsArray) {
                        versions.add(versionNode.asText().trim());
                    }
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
        int idx = findVersionIndex(versions, normalizedCurrent);
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
        
        // locate index rather than doing contains()
        int currentIndex = findVersionIndex(versions, normalizedCurrent);

        if (currentIndex == -1) {
            // Current version not found in list
            logger.warn("[RESOLVER] Current version '{}' not found in version list for state '{}'. " +
                    "Available versions: {}", normalizedCurrent, state, versions);
            return null;
        }

        if (currentIndex < versions.size() - 1) {
            // Return next version in sequence
            String nextVersion = versions.get(currentIndex + 1);
            logger.info("[RESOLVER] Current version '{}' found at index {}. Next version: '{}'", 
                    normalizedCurrent, currentIndex, nextVersion);
            return nextVersion;
        } else {
            // Already at latest version
            logger.info("[RESOLVER] Current version '{}' is at index {} (last). Device is up-to-date.", 
                    normalizedCurrent, currentIndex);
            return null;
        }
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
}
