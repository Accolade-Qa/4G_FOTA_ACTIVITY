package com.aepl.atcu.logic;

import org.junit.Test;
import org.junit.Assert;

import java.io.File;
import java.io.FileWriter;
import java.nio.file.Files;
import java.util.Arrays;


public class FirmwareResolverTest {

    /**
     * Create a temporary servers.json file containing a couple of states with
     * abbreviations so that the resolver can map them.
     */
    private File createTempJson() throws Exception {
        File temp = File.createTempFile("servers", ".json");
        temp.deleteOnExit();
        String json = "[\n" +
                "  {\n" +
                "    \"state\": \"Maharashtra\",\n" +
                "    \"stateAbbreviation\": \"MH\",\n" +
                "    \"firmware\": []\n" +
                "  },\n" +
                "  {\n" +
                "    \"state\": \"Bihar\",\n" +
                "    \"stateAbbreviation\": \"BR\",\n" +
                "    \"firmware\": []\n" +
                "  }\n" +
                "]";
        try (FileWriter w = new FileWriter(temp)) {
            w.write(json);
        }
        return temp;
    }

    @Test
    public void resolveStateName_shouldReturnFullName() throws Exception {
        File json = createTempJson();
        FirmwareResolver resolver = new FirmwareResolver(json.getAbsolutePath());
        Assert.assertEquals("Maharashtra", resolver.resolveStateName("MH"));
        Assert.assertEquals("Bihar", resolver.resolveStateName("BR"));
        Assert.assertNull(resolver.resolveStateName("XX"));
    }
}
