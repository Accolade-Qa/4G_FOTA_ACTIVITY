package com.aepl.atcu.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Assert;
import org.junit.Test;

import java.io.File;
import java.nio.file.Files;
import java.util.List;

public class LoginPacketStoreTest {

    private static final ObjectMapper mapper = new ObjectMapper();

    @Test
    public void testJsonSerializationRoundtrip() throws Exception {
        LoginPacketInfo info = new LoginPacketInfo("123456789012345", "ICCID123", "ACON0001", "1.0.0", "VIN123",
                "MODEL", "STATE");

        String json = mapper.writeValueAsString(info);
        LoginPacketInfo des = mapper.readValue(json, LoginPacketInfo.class);
        Assert.assertEquals(info.imei, des.imei);
        Assert.assertEquals(info.uin, des.uin);
        Assert.assertEquals(info.version, des.version);
        Assert.assertEquals(info.state, des.state);
    }

    @Test
    public void testPersistAndLoadUnique() throws Exception {
        File temp = Files.createTempFile("login", ".json").toFile();
        temp.deleteOnExit();

        LoginPacketInfo a = new LoginPacketInfo("111111111111111", "ICCID1", "ACON001", "v1", "VIN1", "", "");
        LoginPacketInfo b = new LoginPacketInfo("222222222222222", "ICCID2", "ACON002", "v2", "VIN2", "", "");

        // initially empty
        List<LoginPacketInfo> empty = LoginPacketStore.loadAll(temp.getAbsolutePath());
        Assert.assertTrue(empty.isEmpty());

        LoginPacketStore.persist(temp.getAbsolutePath(), a);
        List<LoginPacketInfo> list1 = LoginPacketStore.loadAll(temp.getAbsolutePath());
        Assert.assertEquals(1, list1.size());
        Assert.assertEquals("ACON001", list1.get(0).uin);

        // add second
        LoginPacketStore.persist(temp.getAbsolutePath(), b);
        List<LoginPacketInfo> list2 = LoginPacketStore.loadAll(temp.getAbsolutePath());
        Assert.assertEquals(2, list2.size());

        // add duplicate of first (same uin+version+imei), count should remain 2
        LoginPacketStore.persist(temp.getAbsolutePath(), a);
        List<LoginPacketInfo> list3 = LoginPacketStore.loadAll(temp.getAbsolutePath());
        Assert.assertEquals(2, list3.size());
    }
}
