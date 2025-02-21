#pragma once

#include "btraitable_processor.h"
#include "bflags.h"

class BCache;
class BTraitable;
class BTraitableProcessor;

class BTraitFlags {
public:
    //---- Trait Flags
    inline static const unsigned RESERVED     = 0x1;
    inline static const unsigned ID           = 0x2;
    inline static const unsigned HASH         = 0x4;
    inline static const unsigned READONLY     = 0x8;
    inline static const unsigned NOT_EMPTY    = 0x10;
    inline static const unsigned RUNTIME      = 0x20;
    inline static const unsigned EMBEDDED     = 0x40;
    inline static const unsigned EVAL_ONCE    = 0x80;
    inline static const unsigned EXPENSIVE    = 0x100;

private:
    inline static const unsigned LAST_FLAG = EXPENSIVE;

    static const BFlags* flag(const unsigned v)     { return new BFlags(v); }
};

class BTrait {
public:

    unsigned        m_flags = 0x0;

    py::str         m_name;

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

    py::object      f_is_acceptable_type;   //                      bool    f(obj, trait, value_or_type)
    py::object      f_style_sheet;

    //    auto bound_f_get = [f_get, X, Y]() {
    //        return f_get(X, Y);
    //    };
    //
    //    // Call the bound function
    //    py::object result = bound_f_get();

protected:

    void raise(py::error_already_set& exc, BTraitable* obj, const py::object& f, const py::object* value, const py::args* args);

    virtual BasicNode*  find_node(BTraitableProcessor* proc, BTraitable* obj);
    virtual BasicNode*  find_node(BTraitableProcessor* proc, BTraitable* obj, const py::args& args);

    virtual BasicNode*  find_or_create_node(BTraitableProcessor* proc, BTraitable* obj, int node_type);
    virtual BasicNode*  find_or_create_node(BTraitableProcessor* proc, BTraitable* obj, int node_type, const py::args& args);

public:

    BTrait();
    BTrait(const BTrait& src) = default;

    [[nodiscard]] bool flags_on(unsigned flags) const       { return m_flags & flags; }
    [[nodiscard]] bool flags_on(const BFlags& flags) const  { return m_flags & flags.value(); }
    void set_flags(unsigned flags_to_set)                   { m_flags |= flags_to_set; }
    void reset_flags(unsigned flags_to_reset)               { m_flags &= ~flags_to_reset; }
    void modify_flags(unsigned to_set, unsigned to_reset)   { m_flags = (m_flags | to_set) & ~to_reset; }

    void set_f_get(py::object f)                            { f_get = f; }
    void set_f_set(py::object f)                            { f_set = f; }
    void set_f_verify(py::object f)                         { f_verify = f; }
    void set_f_from_str(py::object f)                       { f_from_str = f; }
    void set_f_from_any_xstr(py::object f)                  { f_from_any_xstr = f; }
    void set_f_to_str(py::object f)                         { f_to_str = f; }
    void set_f_serialize(py::object f)                      { f_serialize = f; }
    void set_f_deserialize(py::object f)                    { f_deserialize = f; }
    void set_f_to_id(py::object f)                          { f_to_id = f; }

    //-- Trait Method wrappers

    py::object wrapper_f_get(BTraitable* obj);
    py::object wrapper_f_get(BTraitable* obj, const py::args& args);

    py::object wrapper_f_set(BTraitable* obj, const py::object& value);
    py::object wrapper_f_set(BTraitable* obj, const py::object& value, const py::args& args);

    py::object wrapper_f_verify(BTraitable* obj, const py::object& value);
    py::object wrapper_f_from_str(BTraitable* obj, const py::object& value);
    py::object wrapper_f_from_any_xstr(BTraitable* obj, const py::object& value);
    py::object wrapper_f_to_str(BTraitable* obj, const py::object& value);
    py::object wrapper_f_serialize(BTraitable* obj, const py::object& value);
    py::object wrapper_f_deserialize(BTraitable* obj, const py::object& value);
    py::object wrapper_f_to_id(BTraitable* obj, const py::object& value);

    //---- Getting trait value

    virtual py::object  get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj);
    virtual py::object  get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args);

    virtual py::object  get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj);
    virtual py::object  get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args);

    //---- Invalidating trait value

    virtual void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj);
    virtual void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args);

    virtual void invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj);
    virtual void invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args);

    //---- Setting (raw) trait value

    virtual py::object raw_set_value_off_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value);
    virtual py::object raw_set_value_off_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args );

    virtual py::object raw_set_value_off_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value);
    virtual py::object raw_set_value_off_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args);

    virtual py::object raw_set_value_off_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value);
    virtual py::object raw_set_value_off_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args);

    virtual py::object raw_set_value_on_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value);
    virtual py::object raw_set_value_on_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args);

    virtual py::object raw_set_value_on_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value);
    virtual py::object raw_set_value_on_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args);

    virtual py::object raw_set_value_on_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value);
    virtual py::object raw_set_value_on_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args);

};

class EvalOnceTrait : public BTrait {
    void dont_touch_me(BTraitable* obj);

public:

    py::object get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj) final;
    py::object get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) final;

    py::object get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj) final {
        return EvalOnceTrait::get_value_off_graph(proc, obj);
    }

    py::object get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) final {
        return EvalOnceTrait::get_value_off_graph(proc, obj, args);
    }

    void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj) final {
        dont_touch_me(obj);
    }

    void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) final {
        dont_touch_me(obj);
    }

    void invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj) final {
        dont_touch_me(obj);
    }

    void invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) final {
        dont_touch_me(obj);
    }

    py::object raw_set_value_off_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) final {
        dont_touch_me(obj);
        return PyLinkage::RC_TRUE();
    }

    py::object raw_set_value_off_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) final {
        dont_touch_me(obj);
        return PyLinkage::RC_TRUE();
    }

    py::object raw_set_value_off_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value);
    }

    py::object raw_set_value_off_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value, args);
    }

    py::object raw_set_value_off_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value);
    }

    py::object raw_set_value_off_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value, args);
    }

    py::object raw_set_value_on_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value);
    }

    py::object raw_set_value_on_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value, args);
    }

    py::object raw_set_value_on_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value);
    }

    py::object raw_set_value_on_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) final  {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value, args);
    }

    py::object raw_set_value_on_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value);
    }

    py::object raw_set_value_on_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) final {
        return EvalOnceTrait::raw_set_value_off_graph_noconvert_nocheck(proc, obj, value, args);
    }

};

//class IdTrait : public BTrait {
//    bool    m_hashed;
//
//public:
//
//    void set_hashed(bool hashed)                { m_hashed = hashed; }
//    [[nodiscard]] bool is_hashed() const        { return m_hashed; }
//
//    [[nodiscard]] bool is_id() const final      { return true; }
//
//    py::object get_value(BTraitable* obj);
//    BRC set_value(BTraitable* obj, const py::object& value);
//
//};