def test_e2e_05_gdpr_info_and_export_zip(verified_user_session):
    _user, client = verified_user_session

    info = client.get("/api/gdpr/info")
    assert info.status_code == 200, info.text
    data = info.json()
    assert data.get("data_stored") is not None
    rights = data.get("gdpr_rights") or {}
    assert rights.get("export") == "/api/gdpr/export"

    export = client.post("/api/gdpr/export")
    assert export.status_code == 200

    # StreamingResponse should set a ZIP content-type
    ctype = export.headers.get("content-type", "")
    assert "application/zip" in ctype

    disp = export.headers.get("content-disposition", "")
    assert "attachment" in disp.lower()

    # Validate ZIP structure
    import io
    import zipfile

    z = zipfile.ZipFile(io.BytesIO(export.content))
    names = set(z.namelist())
    assert "export_manifest.json" in names
    assert "profile.json" in names
    assert "conversations.json" in names
