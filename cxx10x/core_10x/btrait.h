#pragma once

#include <cstdint>

#include "btraitable_processor.h"
#include "bflags.h"
#include "btrait_processor.h"

class BTraitable;
class BTraitableProcessor;

class BTraitFlags {
public:
    //---- Trait Flags
    static constexpr unsigned RESERVED       = 0x1;
    static constexpr unsigned ID             = 0x2;
    static constexpr unsigned HASH           = 0x4;
    static constexpr unsigned READONLY       = 0x8;
    static constexpr unsigned NOT_EMPTY      = 0x10;
    static constexpr unsigned RUNTIME        = 0x20;
    static constexpr unsigned EMBEDDED       = 0x40;
    static constexpr unsigned EVAL_ONCE      = 0x80;
    static constexpr unsigned EXPENSIVE      = 0x100;
    static constexpr unsigned HIDDEN         = 0x200;
    static constexpr unsigned FAUX           = 0x300;
    static constexpr unsigned ID_LIKE        = ID|FAUX;

    static constexpr unsigned LAST_FLAG = ID_LIKE; //TODO: remove?

    // TODO: review the below CUSTOM_F_*- they do not seem to be used anywhere..
    static constexpr uint64_t CUSTOM_F_GET           = static_cast<uint64_t>(0x1)       << 32;
    static constexpr uint64_t CUSTOM_F_VERIFY        = static_cast<uint64_t>(0x2)       << 32;
    static constexpr uint64_t CUSTOM_F_FROM_STR      = static_cast<uint64_t>(0x4)       << 32;
    static constexpr uint64_t CUSTOM_F_FROM_ANY_XSTR = static_cast<uint64_t>(0x8)       << 32;
    static constexpr uint64_t CUSTOM_F_TO_STR        = static_cast<uint64_t>(0x10)      << 32;
    static constexpr uint64_t CUSTOM_F_SERIALIZE     = static_cast<uint64_t>(0x20)      << 32;
    static constexpr uint64_t CUSTOM_F_TO_ID         = static_cast<uint64_t>(0x40)      << 32;
    static constexpr uint64_t CUSTOM_F_CHOICES       = static_cast<uint64_t>(0x80)      << 32;

    static const BFlags* flag(const unsigned v)     { return new BFlags(v); }
};

class BTrait {
    bool            m_getter_has_args;
public:
    BTraitProcessor*    m_proc = nullptr;

    uint64_t        m_flags = 0x0;

    py::object      m_name;
    std::string     m_cpp_name;

    py::object      m_datatype;     // XNone, must be set to a py class from py
    py::object      m_default;      // XNone, may be set to a concrete instance of m_datatype from py

    py::object      f_get;              // value getter from py         ANY     f(obj, [*args])
    py::object      f_set;              // value setter from py         RC      f(obj, trait, value, [*args])
    py::object      f_verify;           // value verifier from py       RC      f(obj, trait, value)
    py::object      f_from_str;         // string converter from py     RC      f(obj, trait, value: str)
    py::object      f_from_any_xstr;    // data converter from py       RC      f(obj, trait, value)
    py::object      f_to_str;           // value formatter from py      str     f(obj, trait, value)
    py::object      f_serialize;        // serialize value              ANY     f(obj, trait, value)
    py::object      f_deserialize;      // deserialize value            RC      f(obj, trait, value)
    py::object      f_to_id;            // value to ID                  str     f(obj, trait, value)
    py::object      f_choices;          // optional choices             ANY     f(obj, trait)

    py::object      f_is_acceptable_type;   //                      bool    f(obj, trait, value_or_type)
    py::object      f_style_sheet;      // style sheet from py          dict    f(obj, trait)

protected:
    py::error_already_set trait_error(const py::error_already_set& exc, BTraitable* obj, const BTraitableClass* cls, const py::object& f, const py::object* value, const py::args* args) const;
    py::error_already_set trait_error(const py::error_already_set& exc, const BTraitableClass* cls, const py::object& f, const py::object* value, const py::args* args) const {
        return trait_error(exc, nullptr, cls, f, value, args);
    }
    py::error_already_set trait_error(const py::error_already_set& exc, BTraitable* obj, const py::object& f, const py::object* value, const py::args* args) const {
        return trait_error(exc, obj, nullptr, f, value, args);
    }


public:

    BTrait();
    BTrait(const BTrait& src) = default;
    ~BTrait()   { delete m_proc; }

    void create_proc();

    [[nodiscard]]BTraitProcessor* proc() const                      { return m_proc; }

    void set_getter_has_args()                                      { m_getter_has_args = true; }
    [[nodiscard]]bool getter_has_args() const                       { return m_getter_has_args; }

    void set_name(const py::object& name) {
        m_name = name;
        m_cpp_name = name.cast<std::string>();
    }

    [[nodiscard]] const std::string& cpp_name() const               { return m_cpp_name; }

    [[nodiscard]] const py::object& name() const                    { return m_name; }
    [[nodiscard]] const py::object& data_type() const               { return m_datatype; }
    [[nodiscard]] bool flags_on(const uint64_t flags) const         { return m_flags & flags; }
    [[nodiscard]] bool has_custom_getter() const                    { return m_flags & BTraitFlags::CUSTOM_F_GET; }

    [[nodiscard]] bool flags_on(const BFlags& flags) const          { return m_flags & flags.value(); }
    void set_flags(uint64_t flags_to_set)                           { m_flags |= flags_to_set; }
    void reset_flags(uint64_t flags_to_reset)                       { m_flags &= ~flags_to_reset; }
    void modify_flags(uint64_t to_set, uint64_t to_reset)           { m_flags = (m_flags | to_set) & ~to_reset; }

    void set_f_get(const py::object &f, bool custom)               { f_get = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_GET; }
    void set_f_set(const py::object &f, bool custom)               { f_set = f; }
    void set_f_verify(const py::object &f, bool custom)            { f_verify = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_VERIFY; }
    void set_f_from_str(const py::object &f, bool custom)          { f_from_str = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_FROM_STR; }
    void set_f_from_any_xstr(const py::object &f, bool custom)     { f_from_any_xstr = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_FROM_ANY_XSTR; }
    void set_f_to_str(const py::object &f, bool custom)            { f_to_str = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_TO_STR; }
    void set_f_serialize(const py::object &f, bool custom)         { f_serialize = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_SERIALIZE; }
    void set_f_is_acceptable_type(const py::object &f, bool custom) { f_is_acceptable_type = f; }
    void set_f_deserialize(const py::object &f, bool custom)       { f_deserialize = f; }
    void set_f_to_id(const py::object &f, bool custom)             { f_to_id = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_TO_ID; }
    void set_f_choices(const py::object &f, bool custom)           { f_choices = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_CHOICES; }
    void set_f_style_sheet(const py::object &f, bool custom)       { f_style_sheet = f; }

    //-- Trait Method wrappers

    py::object wrapper_f_get(BTraitable* obj) const;
    py::object wrapper_f_get(BTraitable* obj, const py::args& args) const;

    py::object wrapper_f_set(BTraitable* obj, const py::object& value) const;
    py::object wrapper_f_set(BTraitable* obj, const py::object& value, const py::args& args) const;

    py::object wrapper_f_verify(BTraitable* obj) const;
    py::object wrapper_f_verify(BTraitable* obj, const py::object& value) const;

    py::object wrapper_f_from_str(BTraitable* obj, const py::object& value) const;
    py::object wrapper_f_from_any_xstr(BTraitable* obj, const py::object& value) const;
    py::object wrapper_f_to_str(BTraitable* obj, const py::object& value) const;
    bool       wrapper_f_is_acceptable_type(BTraitable* obj, const py::object& value) const;
    py::object wrapper_f_serialize(const BTraitableClass* cls, const py::object& value) const;
    py::object wrapper_f_deserialize(const BTraitableClass* cls, const py::object& value) const;
    py::object wrapper_f_to_id(BTraitable* obj, const py::object& value) const;
    py::object wrapper_f_choices(BTraitable* obj) const;
    py::object wrapper_f_style_sheet(BTraitable* obj) const;

    // TODO: review the below custom_f_*- they do not seem to be used anywhere..
    [[nodiscard]] py::object custom_f_get() const           { return m_flags & BTraitFlags::CUSTOM_F_GET ? f_get : py::none(); }
    [[nodiscard]] py::object custom_f_set() const           { return f_set; }
    [[nodiscard]] py::object custom_f_verify() const        { return m_flags & BTraitFlags::CUSTOM_F_VERIFY ? f_verify : py::none(); }
    [[nodiscard]] py::object custom_f_from_str() const      { return m_flags & BTraitFlags::CUSTOM_F_FROM_STR ? f_from_str : py::none(); }
    [[nodiscard]] py::object custom_f_from_any_xstr() const { return m_flags & BTraitFlags::CUSTOM_F_FROM_ANY_XSTR ? f_from_any_xstr : py::none(); }
    [[nodiscard]] py::object custom_f_to_str() const        { return m_flags & BTraitFlags::CUSTOM_F_TO_STR ? f_to_str : py::none(); }
    [[nodiscard]] py::object custom_f_serialize() const     { return m_flags & BTraitFlags::CUSTOM_F_SERIALIZE ? f_serialize : py::none(); }
    [[nodiscard]] py::object custom_f_to_id() const         { return m_flags & BTraitFlags::CUSTOM_F_TO_ID ? f_to_id : py::none(); }
    [[nodiscard]] py::object custom_f_choices() const       { return m_flags & BTraitFlags::CUSTOM_F_CHOICES ? f_choices : py::none(); }
    [[nodiscard]] py::object custom_f_style_sheet() const   { return f_style_sheet; }

};

