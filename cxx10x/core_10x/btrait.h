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
    inline static const unsigned RESERVED       = 0x1;
    inline static const unsigned ID             = 0x2;
    inline static const unsigned HASH           = 0x4;
    inline static const unsigned READONLY       = 0x8;
    inline static const unsigned NOT_EMPTY      = 0x10;
    inline static const unsigned RUNTIME        = 0x20;
    inline static const unsigned EMBEDDED       = 0x40;
    inline static const unsigned EVAL_ONCE      = 0x80;
    inline static const unsigned EXPENSIVE      = 0x100;
    inline static const unsigned HIDDEN         = 0x200;

    inline static const unsigned LAST_FLAG = HIDDEN;

    // TODO: review the below CUSTOM_F_*- they do not seem to be used anywhere..
    inline static const uint64_t CUSTOM_F_GET           = uint64_t(0x1)       << 32;
    inline static const uint64_t CUSTOM_F_VERIFY        = uint64_t(0x2)       << 32;
    inline static const uint64_t CUSTOM_F_FROM_STR      = uint64_t(0x4)       << 32;
    inline static const uint64_t CUSTOM_F_FROM_ANY_XSTR = uint64_t(0x8)       << 32;
    inline static const uint64_t CUSTOM_F_TO_STR        = uint64_t(0x10)      << 32;
    inline static const uint64_t CUSTOM_F_SERIALIZE     = uint64_t(0x20)      << 32;
    inline static const uint64_t CUSTOM_F_TO_ID         = uint64_t(0x40)      << 32;
    inline static const uint64_t CUSTOM_F_CHOICES       = uint64_t(0x80)      << 32;

    static const BFlags* flag(const unsigned v)     { return new BFlags(v); }
};

class BTrait {
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
    py::error_already_set trait_error(py::error_already_set& exc, BTraitable* obj, BTraitableClass* cls, const py::object& f, const py::object* value, const py::args* args);
    py::error_already_set trait_error(py::error_already_set& exc, BTraitableClass* cls, const py::object& f, const py::object* value, const py::args* args) {
        return trait_error(exc, nullptr, cls, f, value, args);
    }
    py::error_already_set trait_error(py::error_already_set& exc, BTraitable* obj, const py::object& f, const py::object* value, const py::args* args) {
        return trait_error(exc, obj, nullptr, f, value, args);
    }


public:

    BTrait();
    BTrait(const BTrait& src) = default;
    ~BTrait()   { delete m_proc; }

    void create_proc();

    [[nodiscard]]BTraitProcessor* proc() const              { return m_proc; }

    void set_name(const py::object& name) {
        m_name = name;
        m_cpp_name = name.cast<std::string>();
    }

    [[nodiscard]] const std::string& cpp_name() const       { return m_cpp_name; }

    [[nodiscard]] const py::object& name() const            { return m_name; }
    [[nodiscard]] const py::object& data_type() const       { return m_datatype; }
    [[nodiscard]] bool flags_on(uint64_t flags) const       { return m_flags & flags; }

    [[nodiscard]] bool flags_on(const BFlags& flags) const  { return m_flags & flags.value(); }
    void set_flags(uint64_t flags_to_set)                   { m_flags |= flags_to_set; }
    void reset_flags(uint64_t flags_to_reset)               { m_flags &= ~flags_to_reset; }
    void modify_flags(uint64_t to_set, uint64_t to_reset)   { m_flags = (m_flags | to_set) & ~to_reset; }

    void set_f_get(py::object f, bool custom)               { f_get = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_GET; }
    void set_f_set(py::object f, bool custom)               { f_set = f; }
    void set_f_verify(py::object f, bool custom)            { f_verify = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_VERIFY; }
    void set_f_from_str(py::object f, bool custom)          { f_from_str = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_FROM_STR; }
    void set_f_from_any_xstr(py::object f, bool custom)     { f_from_any_xstr = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_FROM_ANY_XSTR; }
    void set_f_to_str(py::object f, bool custom)            { f_to_str = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_TO_STR; }
    void set_f_serialize(py::object f, bool custom)         { f_serialize = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_SERIALIZE; }
    void set_f_is_acceptable_type(py::object f, bool custom) { f_is_acceptable_type = f; }
    void set_f_deserialize(py::object f, bool custom)       { f_deserialize = f; }
    void set_f_to_id(py::object f, bool custom)             { f_to_id = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_TO_ID; }
    void set_f_choices(py::object f, bool custom)           { f_choices = f; if (custom) m_flags |= BTraitFlags::CUSTOM_F_CHOICES; }
    void set_f_style_sheet(py::object f, bool custom)       { f_style_sheet = f; }

    //-- Trait Method wrappers

    py::object wrapper_f_get(BTraitable* obj);
    py::object wrapper_f_get(BTraitable* obj, const py::args& args);

    py::object wrapper_f_set(BTraitable* obj, const py::object& value);
    py::object wrapper_f_set(BTraitable* obj, const py::object& value, const py::args& args);

    py::object wrapper_f_verify(BTraitable* obj, const py::object& value);
    py::object wrapper_f_from_str(BTraitable* obj, const py::object& value);
    py::object wrapper_f_from_any_xstr(BTraitable* obj, const py::object& value);
    py::object wrapper_f_to_str(BTraitable* obj, const py::object& value);
    bool       wrapper_f_is_acceptable_type(BTraitable* obj, const py::object& value);
    py::object wrapper_f_serialize(BTraitableClass* cls, const py::object& value);
    py::object wrapper_f_deserialize(BTraitableClass* cls, const py::object& value);
    py::object wrapper_f_to_id(BTraitable* obj, const py::object& value);
    py::object wrapper_f_choices(BTraitable* obj);
    py::object wrapper_f_style_sheet(BTraitable* obj);

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

