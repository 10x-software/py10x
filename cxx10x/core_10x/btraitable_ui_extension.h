//
// Created by AMD on 3/3/2025.
//

#pragma once

#include <unordered_map>

#include "py_linkage.h"

class BTraitableClass;
class BTraitable;
class BTrait;

class BUiClass {
    using Dir = std::unordered_map<BTrait*, BTrait*>;

    BTraitableClass*    m_class;
    Dir                 m_own_dir;

public:
    explicit BUiClass(BTraitableClass* cls);

    BTrait *bui_trait(BTrait *trait) const;

    void create_ui_node(BTraitable* obj, BTrait* trait, py::object f_refresh);
    void update_ui_node(BTraitable* obj, BTrait* trait);
};
