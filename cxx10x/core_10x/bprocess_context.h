//
// Created by AMD on 5/20/2024.
//
#pragma once

class BProcessContext {
public:
    //-- Unsigned properties by topic
    inline static const unsigned  TP_TYPE       = 0;    //-- Trait Processor Type
    //...
    inline static const unsigned  N_UNS_TOPICS  = 1;    //-- count

    //-- Flags
    inline static const unsigned  CACHE_ONLY    = 0x1;
    //...

private:
    unsigned    m_flags;
    unsigned    m_uns_topics[N_UNS_TOPICS];

    void check_uns_t(unsigned t) const;

public:

    static BProcessContext  PC;

    BProcessContext();

    [[nodiscard]] bool      flags_on(unsigned flags) const                      { return m_flags & flags; }
    void                    set_flags(unsigned to_set, unsigned to_reset = 0x0) { m_flags = (m_flags | to_set) & ~to_reset; }

    [[nodiscard]] unsigned  topic(unsigned t) const;
    void                    set_topic(unsigned t, unsigned value);

};

