# Roadmap

## Towards v0.2

- **Environment Vars**
  - XX_GRAPH_ON - If True, the default exec mode is GRAPH_ON (done)
  

- **Automatic Resource Access with Authentication**
  - runme_1st_app
  - command line utilities

- **Kernel**
  - runtime - allow getting traitable IDs by class from the current Cache through Cache parents, if any (done)
  
- **Core**
  - Added Traitable.existing_instances_by_filter()
  - Added T.OFFGRAPH_SET - in GRAPG_OFF mode, on get_value() sets it as well, if not already
  - Added embeddable flag for Traitable subclass to allow embeddable Traitables not to be derived from AnonynousTraitable
  - Added Basketable facility (use case: Portfolio -> Book -> Trade -> FinBasket -> FinInstrument ->...)
    - also planned to be used in parallelization
  
  
- **Finish UI Table Integration**
  - examples.guess_word game (done)
  - examples.stock_simulator (done)
  - use *trait-name*_action(self) method for callback of Ui.PUSH_BUTTON trait (done)