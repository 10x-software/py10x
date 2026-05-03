if __name__ == '__main__':
    from core_10x.vault_utils import VaultUtils
    #from core_10x.exec_control import DEBUG_ON

    #with DEBUG_ON():
    rc = VaultUtils.admin_save_user_credentials()
    if not rc:
        print(rc.error())