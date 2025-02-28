//
// Created by AMD on 4/16/2024.
//
#pragma once

#include <sstream>
#include <stdint.h>

class BFlags {
    uint64_t        m_flags;
    //std::string     m_name;

public:
    static uint64_t modify(uint64_t state, uint64_t flags_to_set, uint64_t flags_to_reset)
    {
        return (state | flags_to_set) & ~flags_to_reset;
    }

    static bool check(uint64_t state, uint64_t flags_set, uint64_t flags_reset)
    {
        bool res = state & flags_set;
        if (!flags_reset)
            return res;

        return res && (state & flags_reset) == 0x0;
    }

    BFlags() : BFlags(0x0)                                              {}
    BFlags(const BFlags& flags) = default;
    explicit BFlags(uint64_t v) : m_flags(v)                            {}

    [[nodiscard]] uint64_t value() const                                { return m_flags; }
    [[nodiscard]] bool on(const BFlags& flags) const                    { return m_flags & flags.m_flags; }
    [[nodiscard]] bool off(const BFlags& flags) const                   { return (m_flags & flags.m_flags) == 0x0; }

    [[nodiscard]] bool on_off(const BFlags& flags_on, const BFlags& flags_off) const
    {
        return check(m_flags, flags_on.m_flags, flags_off.m_flags);
    }

    void set(uint64_t flags)                                            { m_flags |= flags; }
    void reset(uint64_t flags)                                          { m_flags &= ~flags; }
    void set_reset(uint64_t to_set, uint64_t to_reset)                  { m_flags = (m_flags | to_set) & ~to_reset; }

    void next()                                                         { m_flags <<= 1; }

    [[nodiscard]] BFlags add(const BFlags& other) const                 { return BFlags(m_flags | other.m_flags); }
    [[nodiscard]] BFlags sub(const BFlags& other) const                 { return BFlags(m_flags & ~other.m_flags); }

    [[nodiscard]] std::string repr() const {
        std::stringstream ss;
        ss << "0x" << std::hex << m_flags;
        return ss.str();
    }

};

