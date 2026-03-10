if __name__ == '__main__':

    from core_10x.logger import Logger, LOG

    Logger.init('test_logger')

    LOG('First message')
    LOG(dict(a = 1, b = 'ccc'))
    LOG('Regular message')

    LOG('Last message')
    LOG(None)
