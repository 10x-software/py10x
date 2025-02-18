//
// Created by AMD on 1/22/2025.
//

#pragma once

#include <functional>

namespace hasher10x {

    //    std::size_t combine_hashes(std::initializer_list<std::size_t> hashes) {
    //        std::size_t seed = 0;
    //        for (auto hash : hashes)
    //            seed ^= hash + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    //
    //        return seed;
    //    }

    void add_hash(std::size_t& seed, std::size_t value) {
        seed ^= value + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    }

    std::size_t from_hashes(std::size_t hash1, std::size_t hash2) {
        std::size_t seed = 0;
        add_hash(seed, hash1);
        add_hash(seed, hash2);
        return seed;
    }

    template <typename T>
    void add_value(std::size_t& seed, const T& value) {
        std::hash<T> hasher;
        add_hash(seed, hasher(value));
    }

    template <typename... Types>
    std::size_t from_values(const Types&... values) {
        std::size_t seed = 0;
        (add_value(seed, values), ...);
        return seed;
    }

};

