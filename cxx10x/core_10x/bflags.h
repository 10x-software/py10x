//
// Created by AMD on 4/16/2024.
//
#pragma once

#include <sstream>

class BFlags {
    unsigned        m_flags;
    //std::string     m_name;

public:
    static unsigned modify(unsigned state, unsigned flags_to_set, unsigned flags_to_reset)
    {
        return (state | flags_to_set) & ~flags_to_reset;
    }

    static bool check(unsigned state, unsigned flags_set, unsigned flags_reset)
    {
        bool res = state & flags_set;
        if (!flags_reset)
            return res;

        return res && (state & flags_reset) == 0x0;
    }

    BFlags() : BFlags(0x0)                                              {}
    BFlags(const BFlags& flags) = default;
    explicit BFlags(unsigned v) : m_flags(v)                            {}

    [[nodiscard]] unsigned value() const                                { return m_flags; }
    [[nodiscard]] bool on(const BFlags& flags) const                    { return m_flags & flags.m_flags; }
    [[nodiscard]] bool off(const BFlags& flags) const                   { return (m_flags & flags.m_flags) == 0x0; }

    [[nodiscard]] bool on_off(const BFlags& flags_on, const BFlags& flags_off) const
    {
        return check(m_flags, flags_on.m_flags, flags_off.m_flags);
    }

    void set(unsigned flags)                                            { m_flags |= flags; }
    void reset(unsigned flags)                                          { m_flags &= ~flags; }
    void set_reset(unsigned to_set, unsigned to_reset)                  { m_flags = (m_flags | to_set) & ~to_reset; }

    void next()                                                         { m_flags <<= 1; }

    [[nodiscard]] BFlags add(const BFlags& other) const                 { return BFlags(m_flags | other.m_flags); }
    [[nodiscard]] BFlags sub(const BFlags& other) const                 { return BFlags(m_flags & ~other.m_flags); }

    [[nodiscard]] std::string repr() const {
        std::stringstream ss;
        ss << "0x" << std::hex << m_flags;
        return ss.str();
    }

};

