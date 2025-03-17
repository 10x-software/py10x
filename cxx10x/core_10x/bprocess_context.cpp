//
// Created by AMD on 5/22/2024.
//
#include "bprocess_context.h"
#include "btraitable_processor.h"

BProcessContext BProcessContext::PC;

BProcessContext::BProcessContext() {
    //m_flags = CACHE_ONLY;
    m_uns_topics[TP_TYPE] = BTraitableProcessor::PLAIN;
}

void BProcessContext::check_uns_t(unsigned int t) const {
    if (t >= N_UNS_TOPICS)
        throw py::value_error(py::str("Unknown topic {}").format(t));
}

unsigned BProcessContext::topic(unsigned t) const {
    check_uns_t(t);
    return m_uns_topics[t];
}

void BProcessContext::set_topic(unsigned t, unsigned value) {
    check_uns_t(t);
    m_uns_topics[t] = value;
}

