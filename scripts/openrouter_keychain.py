#!/usr/bin/env python3
"""Store/read the OpenRouter key through the native macOS Keychain API.

The secret is entered with hidden terminal input and is never passed as a
command-line argument, printed, or written to the project.
"""

from __future__ import annotations

import ctypes
import getpass
import os


SERVICE = "Baron3x3-Local-OpenRouter"
ACCOUNT = getpass.getuser()
ERR_SEC_ITEM_NOT_FOUND = -25300
ERR_SEC_DUPLICATE_ITEM = -25299


def _frameworks():
    security = ctypes.CDLL(
        "/System/Library/Frameworks/Security.framework/Security"
    )
    core = ctypes.CDLL(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )
    security.SecKeychainFindGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainAddGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyAttributesAndData.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    security.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    security.SecKeychainItemFreeContent.restype = ctypes.c_int32
    core.CFRelease.argtypes = [ctypes.c_void_p]
    return security, core


def _bytes(value: str):
    raw = value.encode("utf-8")
    return raw, ctypes.create_string_buffer(raw)


def read_keychain_secret() -> str | None:
    if os.uname().sysname != "Darwin":
        return None
    security, core = _frameworks()
    service_raw, service = _bytes(SERVICE)
    account_raw, account = _bytes(ACCOUNT)
    length = ctypes.c_uint32()
    data = ctypes.c_void_p()
    item = ctypes.c_void_p()
    status = security.SecKeychainFindGenericPassword(
        None,
        len(service_raw),
        service,
        len(account_raw),
        account,
        ctypes.byref(length),
        ctypes.byref(data),
        ctypes.byref(item),
    )
    if status == ERR_SEC_ITEM_NOT_FOUND:
        return None
    if status != 0:
        raise RuntimeError(f"macOS Keychain zwrócił błąd {status}")
    try:
        return ctypes.string_at(data, length.value).decode("utf-8")
    finally:
        security.SecKeychainItemFreeContent(None, data)
        if item:
            core.CFRelease(item)


def store_keychain_secret(secret: str) -> None:
    if not secret:
        raise ValueError("Pusty klucz")
    security, core = _frameworks()
    service_raw, service = _bytes(SERVICE)
    account_raw, account = _bytes(ACCOUNT)
    secret_raw, secret_buffer = _bytes(secret)
    item = ctypes.c_void_p()
    status = security.SecKeychainAddGenericPassword(
        None,
        len(service_raw),
        service,
        len(account_raw),
        account,
        len(secret_raw),
        secret_buffer,
        ctypes.byref(item),
    )
    if status == ERR_SEC_DUPLICATE_ITEM:
        length = ctypes.c_uint32()
        old_data = ctypes.c_void_p()
        status = security.SecKeychainFindGenericPassword(
            None,
            len(service_raw),
            service,
            len(account_raw),
            account,
            ctypes.byref(length),
            ctypes.byref(old_data),
            ctypes.byref(item),
        )
        if status != 0:
            raise RuntimeError(f"Nie można odnaleźć wpisu Keychain: {status}")
        security.SecKeychainItemFreeContent(None, old_data)
        status = security.SecKeychainItemModifyAttributesAndData(
            item, None, len(secret_raw), secret_buffer
        )
    if item:
        core.CFRelease(item)
    if status != 0:
        raise RuntimeError(f"Nie można zapisać klucza w Keychain: {status}")


def load_openrouter_key() -> str:
    value = os.environ.get("OPENROUTER_API_KEY", "") or read_keychain_secret() or ""
    # Reject malformed values before urllib can produce the misleading 401 "Missing Authentication header".
    if value and (not value.startswith("sk-or-v1-") or any(character.isspace() for character in value)):
        raise RuntimeError("Klucz OpenRouter w środowisku lub Keychainie ma nieprawidłowy format.")
    return value


def main() -> None:
    secret = getpass.getpass("Wklej klucz OpenRouter (wpis jest ukryty): ").strip()
    store_keychain_secret(secret)
    print(f"Klucz zapisany bezpiecznie w macOS Keychain: {SERVICE}")
    print("Klucz nie został zapisany w projekcie ani wyświetlony.")


if __name__ == "__main__":
    main()
