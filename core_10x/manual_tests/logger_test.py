if __name__ == '__main__':

    from core_10x.logger import LOG

    LOG.begin('test_logger', log_level = LOG.DETAILED)

    LOG('First message')
    LOG.MEDIUM(dict(a = 1, b = 'ccc'))
    LOG.DETAILED('Detailed message')

    for i in range(10):
        LOG.VERBOSE(f'i = {i}')

    LOG('Last message')
    LOG.end()
