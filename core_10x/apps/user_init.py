if __name__ == '__main__':
    from core_10x.vault_utils import VaultUtils

    rc = VaultUtils.user_init()
    if not rc:
        print(rc.error())