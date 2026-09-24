import asyncio
import gc
import weakref
from datetime import date

import pytest
import rio.testing.browser_client
from core_10x.code_samples.person import Person
from core_10x.exec_control import BTP, CACHE_ONLY, INTERACTIVE
from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.rio.browser_helpers import (
    COLLECTION_EDITOR_TIMEOUT_MS,
    UI_SETTLE_S,
    click_client_button,
    press_rio_button,
    wait_for_dialog_button,
    wait_for_input_values,
    wait_for_js_value,
    wait_for_selectable_item_text,
    wait_until,
)
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext, session_context
from ui_10x.traitable_editor import TraitableEditor
from ui_10x.utils import ux_push_button
from xxcommon.conftest import ts_instance

import rio

_CE_TIMEOUT = COLLECTION_EDITOR_TIMEOUT_MS


@pytest.fixture
def mock_db_ops(monkeypatch):
    with CACHE_ONLY():
        sasha = Person(first_name='Sasha', last_name='Davidovich', weight_lbs=150, _replace=True)
        ilya = Person(first_name='Ilya', last_name='Pevzner', weight_lbs=200, dob=date(1971, 7, 3), _replace=True)
    monkeypatch.setattr(Person, 'load_ids', lambda: [sasha.id(), ilya.id()])
    monkeypatch.setattr(Person, 'load_data', lambda id: {sasha.id(): sasha, ilya.id(): ilya}[id])
    yield


async def test_collection_editor(mock_db_ops) -> None:
    with INTERACTIVE():
        ce: CollectionEditor | None = None
        widget = None

        def on_session_start(session):
            nonlocal ce, widget
            ctx = UserSessionContext()
            ctx.interactive = BTP.current()
            session.attach(ctx)
            with session_context(session):
                ce = CollectionEditor(coll=Collection(cls=Person))
                widget = ce.main_widget()

        app = rio.App(
            name='collection_editor_test',
            build=lambda: DynamicComponent(widget),
            on_session_start=on_session_start,
        )
        async with rio.testing.BrowserClient(app) as test_client:
            await asyncio.sleep(UI_SETTLE_S)

            await wait_for_js_value(
                test_client,
                'document.querySelector(".rio-selectable-item")?.innerText || ""',
                'Ilya|Pevzner',
                timeout_ms=_CE_TIMEOUT,
            )
            await test_client.execute_js('document.querySelector(".rio-selectable-item").click()')
            await asyncio.sleep(UI_SETTLE_S)

            await wait_for_input_values(
                test_client,
                weight_index=7,
                weight='200.00',
                unit_index=8,
                unit='LB',
                timeout_ms=_CE_TIMEOUT,
            )

            edit_button = next(b for b in test_client.get_components(rio.Button) if b.content == 'edit')
            await press_rio_button(test_client, edit_button)
            await wait_for_dialog_button(test_client, 'Ok', timeout_ms=_CE_TIMEOUT)
            await asyncio.sleep(UI_SETTLE_S)

            await wait_for_input_values(
                test_client,
                weight_index=16,
                weight='200.00',
                unit_index=17,
                unit='LB',
                timeout_ms=_CE_TIMEOUT,
            )

            dropdown_button = next(b for b in reversed(tuple(test_client.get_components(rio.Button))) if b.icon == 'material/arrow_downward')
            await press_rio_button(test_client, dropdown_button)
            await wait_for_selectable_item_text(test_client, 'G', timeout_ms=_CE_TIMEOUT)
            await asyncio.sleep(UI_SETTLE_S)

            list_item_id = next(li._id_ for li in test_client.get_components(rio.SimpleListItem) if li.text == 'G')
            await test_client.execute_js(f'''document.querySelector('[dbg-id="{list_item_id}"]').querySelector('.rio-selectable-item').click()''')
            await asyncio.sleep(UI_SETTLE_S)

            await wait_for_input_values(
                test_client,
                weight_index=16,
                weight='90,702.95',
                unit_index=17,
                unit='G',
                timeout_ms=_CE_TIMEOUT,
            )

            ok_button = next(b for b in test_client.get_components(rio.Button) if b.content == 'Ok')
            await press_rio_button(test_client, ok_button)
            await asyncio.sleep(UI_SETTLE_S)

            await wait_for_input_values(
                test_client,
                weight_index=7,
                weight='90,702.95',
                unit_index=8,
                unit='G',
                timeout_ms=_CE_TIMEOUT,
            )

            searchable_list = ce.searchable_list
            test_client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

        wr = weakref.ref(ce)
        del ce
        gc.collect()
        assert wr() is not None, 'select_hook must keep CollectionEditor reachable via the widget tree'

        searchable_list.release()
        if widget is not None:
            widget.component = None
            widget.subcomponent = None
        widget = None
        del searchable_list


async def _open_entity_edit_dialog(test_client, select_text: str = 'Ilya|Pevzner') -> None:
    """Select the (only) listed entity and open the entity-edit dialog via 'edit'."""
    await wait_for_js_value(
        test_client,
        'document.querySelector(".rio-selectable-item")?.innerText || ""',
        select_text,
        timeout_ms=_CE_TIMEOUT,
    )
    await test_client.execute_js('document.querySelector(".rio-selectable-item").click()')
    await asyncio.sleep(UI_SETTLE_S)

    edit_button = next(b for b in test_client.get_components(rio.Button) if b.content == 'edit')
    await press_rio_button(test_client, edit_button)
    await wait_for_dialog_button(test_client, 'Ok', timeout_ms=_CE_TIMEOUT)
    await asyncio.sleep(UI_SETTLE_S)


def _ok_buttons(test_client) -> list:
    return [b for b in test_client.get_components(rio.Button) if b.content == 'Ok']


async def _accept_nested_dialog_and_check_parent_survives(test_client, opener_label: str, outer_ok) -> None:
    """Open the nested dialog for ``opener_label`` (e.g. 'Dob...'), accept it, and assert
    the outer entity-edit dialog (identified by ``outer_ok``) is still open afterwards.

    Uses real mouse-coordinate clicks (``click_client_button``), not the synthetic
    ``element.click()`` of ``press_rio_button`` — Rio's dialog outside-click dismissal
    is coordinate-based, and a same-origin synthetic click carries no real position.
    """
    opener = next(b for b in test_client.get_components(rio.Button) if b.content == opener_label)
    await click_client_button(test_client, opener)
    await asyncio.sleep(UI_SETTLE_S)

    ok_buttons = _ok_buttons(test_client)
    assert len(ok_buttons) == 2, f'expected outer + nested Ok buttons for {opener_label!r}, got {len(ok_buttons)}'
    inner_ok = next(b for b in ok_buttons if b._id_ != outer_ok._id_)

    await click_client_button(test_client, inner_ok)
    await asyncio.sleep(UI_SETTLE_S)

    remaining = _ok_buttons(test_client)
    assert len(remaining) == 1, f'expected only the outer Ok to remain after accepting the {opener_label!r} dialog, got {len(remaining)}'
    assert remaining[0]._id_ == outer_ok._id_, f'outer entity-edit dialog closed when the nested {opener_label!r} dialog was accepted'


async def test_collection_editor_edit_dob_calendar_does_not_close_parent_dialog(mock_db_ops) -> None:
    """Accepting the nested date-picker dialog must not close the outer entity-edit dialog.

    Regression test for ``TraitEditor.date_cb`` opening its ``UxDialog`` without
    ``parent=``: without an owning_component, Rio has nothing tying the nested
    dialog to the one that opened it, and accepting the nested dialog also closed
    the outer one. ``weight_qu``'s ``ChoiceWidget`` popup never had this problem —
    it already passes ``parent=self`` (see ``ChoiceWidget.show_popup``) — which is
    the model the fix follows.
    """
    with INTERACTIVE():
        ce: CollectionEditor | None = None
        widget = None

        def on_session_start(session):
            nonlocal ce, widget
            ctx = UserSessionContext()
            ctx.interactive = BTP.current()
            session.attach(ctx)
            with session_context(session):
                ce = CollectionEditor(coll=Collection(cls=Person))
                widget = ce.main_widget()

        app = rio.App(
            name='collection_editor_dob_test',
            build=lambda: DynamicComponent(widget),
            on_session_start=on_session_start,
        )
        async with rio.testing.BrowserClient(app) as test_client:
            await asyncio.sleep(UI_SETTLE_S)
            await _open_entity_edit_dialog(test_client)

            outer_ok = _ok_buttons(test_client)[0]
            await _accept_nested_dialog_and_check_parent_survives(test_client, 'Dob...', outer_ok)

            # Outer dialog is still functional: its own fields are intact.
            await wait_for_input_values(
                test_client,
                weight_index=16,
                weight='200.00',
                unit_index=17,
                unit='LB',
                timeout_ms=_CE_TIMEOUT,
            )

            ok_button = _ok_buttons(test_client)[0]
            await press_rio_button(test_client, ok_button)
            await asyncio.sleep(UI_SETTLE_S)

            searchable_list = ce.searchable_list
            test_client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

        wr = weakref.ref(ce)
        del ce
        gc.collect()
        assert wr() is not None, 'select_hook must keep CollectionEditor reachable via the widget tree'

        searchable_list.release()
        if widget is not None:
            widget.component = None
            widget.subcomponent = None
        widget = None
        del searchable_list


async def test_traitable_editor_edit_tags_multichoice_does_not_close_parent_dialog() -> None:
    """Same regression as the dob/calendar test above, for ``list_cb`` / MultiChoice.

    Also covers the separate ``accept_callback=lambda ctx: ...`` bug: UxDialog.on_ok()
    always calls ``accept_callback()`` with no arguments, so the stray ``ctx`` parameter
    raised a TypeError that (before the fix) also masked the missing-parent symptom.

    Uses a minimal direct ``TraitableEditor.popup()`` harness (no CollectionEditor /
    EntityStocker) — this is exactly what ``EntityStocker.on_edit_entity`` calls once a
    row is selected, so it exercises the same nested-dialog path as the dob test above.
    """
    with INTERACTIVE():
        with CACHE_ONLY():
            entity = Person(first_name='Widget', last_name='Tagged', tags=['red', 'green', 'blue'], _replace=True)

        ed: TraitableEditor | None = None
        open_button = None

        def open_editor():
            nonlocal ed
            ed = TraitableEditor.editor(entity)
            ed.popup()

        def on_session_start(session):
            nonlocal open_button
            ctx = UserSessionContext()
            ctx.interactive = BTP.current()
            session.attach(ctx)
            with session_context(session):
                open_button = ux_push_button('Open', callback=open_editor)

        app = rio.App(
            name='tags_multichoice_test',
            build=lambda: DynamicComponent(open_button),
            on_session_start=on_session_start,
        )
        async with rio.testing.BrowserClient(app) as test_client:
            await asyncio.sleep(UI_SETTLE_S)

            open_btn = next(b for b in test_client.get_components(rio.Button) if b.content == 'Open')
            await press_rio_button(test_client, open_btn)
            await wait_for_dialog_button(test_client, 'Ok', timeout_ms=_CE_TIMEOUT)
            await asyncio.sleep(UI_SETTLE_S)

            outer_ok = _ok_buttons(test_client)[0]

            opener = next(b for b in test_client.get_components(rio.Button) if b.content == 'Tags...')
            await click_client_button(test_client, opener)
            await asyncio.sleep(UI_SETTLE_S)

            # Selection must reflect the trait's current value: 'red' (like every
            # current tag) should already render twice — once in the source pane,
            # once in the selection pane — with no interaction at all.
            await wait_for_selectable_item_text(test_client, 'red', timeout_ms=_CE_TIMEOUT)
            await wait_until(
                lambda: test_client.execute_js(
                    """[...document.querySelectorAll('.rio-selectable-item')]
                        .filter(el => el.innerText === 'red').length >= 2"""
                ),
                timeout_s=10.0,
                message="'red' to be pre-selected on open",
            )

            ok_buttons = _ok_buttons(test_client)
            assert len(ok_buttons) == 2, f'expected outer + nested Ok buttons, got {len(ok_buttons)}'
            inner_ok = next(b for b in ok_buttons if b._id_ != outer_ok._id_)

            await click_client_button(test_client, inner_ok)
            await asyncio.sleep(UI_SETTLE_S)

            remaining = _ok_buttons(test_client)
            assert len(remaining) == 1, f'expected only the outer Ok to remain, got {len(remaining)}'
            assert remaining[0]._id_ == outer_ok._id_, 'outer entity-edit dialog closed when the nested Tags dialog was accepted'

            # The nested MultiChoice's accept_callback runs under the outer dialog's
            # INTERACTIVE() processor (copy_entity=True) — it stages the change but does
            # not commit it; that happens when the outer dialog's own Ok exports it below.
            await press_rio_button(test_client, remaining[0])
            await asyncio.sleep(UI_SETTLE_S)

            # Nothing was deselected, so accepting must round-trip the original value —
            # this only holds if the selection really was pre-populated from it above.
            assert entity.tags == ['red', 'green', 'blue'], f'expected the pre-populated selection to round-trip unchanged, got {entity.tags}'

            test_client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

        if open_button is not None:
            open_button.component = None
            open_button.subcomponent = None
        open_button = None
        ed = None
        entity = None
        gc.collect()


async def _select_entity(test_client, select_text: str) -> None:
    """Select ``select_text`` among possibly multiple listed entities."""
    find = f'[...document.querySelectorAll(".rio-selectable-item")].find(el => el.innerText === "{select_text}")'
    await wait_for_js_value(test_client, f'({find}) ? "found" : ""', 'found', timeout_ms=_CE_TIMEOUT)
    await test_client.execute_js(f'{find}.click()')
    await asyncio.sleep(UI_SETTLE_S)


async def _press_named_button(test_client, label: str) -> None:
    """Press the currently rendered button labeled ``label``."""
    button = next(b for b in test_client.get_components(rio.Button) if b.content == label)
    await press_rio_button(test_client, button)
    await asyncio.sleep(UI_SETTLE_S)


async def _set_input_value(test_client, index: int, value: str) -> None:
    """Type ``value`` into the input at DOM ``index``.

    focus/input/blur, not a bare ``.value =``: Rio picks the edit up from the input
    event and only commits it to the trait on blur.
    """
    field = f'document.querySelectorAll("input")[{index}]'
    await test_client.execute_js(f'{field}.focus();')
    await test_client.execute_js(f'{field}.value = "{value}";')
    await test_client.execute_js(f'{field}.dispatchEvent(new Event("input"));')
    await test_client.execute_js(f'{field}.blur();')
    await asyncio.sleep(UI_SETTLE_S)


async def _edit_weight_lbs(test_client, select_text: str, new_weight_lbs: str) -> None:
    """Select ``select_text``, open its edit dialog, change ``weight_lbs`` (a plain
    numeric input -- the dialog's 4th field, after first_name/last_name/dob, at a fixed
    DOM index since the dialog always renders the same fields in the same order; the
    read-only viewer pane renders the same entity ahead of it, hence 13 not 4), and
    accept (Ok) without saving.
    """
    await _select_entity(test_client, select_text)

    await _press_named_button(test_client, 'edit')
    await wait_for_dialog_button(test_client, 'Ok', timeout_ms=_CE_TIMEOUT)
    await asyncio.sleep(UI_SETTLE_S)

    await _set_input_value(test_client, 13, new_weight_lbs)

    await _press_named_button(test_client, 'Ok')


async def _click_save(test_client) -> None:
    await _press_named_button(test_client, 'save')


async def test_collection_editor_track_changes_switch_entities_and_save(monkeypatch, ts_instance) -> None:  # noqa: F811
    """track_changes=True end-to-end: edits to two different entities stay isolated in
    their own ``EntityStocker.change_trackers`` entry until each is explicitly saved.
    Switching the current entity, and returning to a previously-edited one, must not
    lose or leak a pending edit across entities -- this is the core contract of
    ``EntityStocker.change_trackers: dict[Traitable, SaveIfChanged]``.

    Backed by a real ``ts_instance`` store (not ``CACHE_ONLY``, unlike ``mock_db_ops``)
    since this test needs a genuine save()/persist round trip. Store setup/teardown is
    inlined here (not a separate fixture) -- under this file's async test conversion, a
    fixture that spans ``with ts_instance, INTERACTIVE():`` across its ``yield`` leaves
    Alice/Bob spuriously reachable at teardown even after they're deleted, tripping the
    isolation suite's leftover-Traitable check; doing the same inline in the test body
    does not.
    """
    with ts_instance, INTERACTIVE():
        alice = Person(first_name='Trackchangesalice', last_name='Trackchangesaliceln', weight_lbs=150, _replace=True)
        bob = Person(first_name='Trackchangesbob', last_name='Trackchangesbobln', weight_lbs=200, dob=date(1971, 7, 3), _replace=True)
        alice.save().throw()
        bob.save().throw()
        monkeypatch.setattr(Person, 'load_ids', lambda: [alice.id(), bob.id()])
        monkeypatch.setattr(Person, 'load_data', lambda id: {alice.id(): alice, bob.id(): bob}[id])

        try:
            ce: CollectionEditor | None = None
            widget = None

            def on_session_start(session):
                nonlocal ce, widget
                ctx = UserSessionContext()
                ctx.interactive = BTP.current()
                session.attach(ctx)
                with session_context(session):
                    ce = CollectionEditor(coll=Collection(cls=Person), track_changes=True)
                    widget = ce.main_widget()

            app = rio.App(
                name='collection_editor_track_changes_test',
                build=lambda: DynamicComponent(widget),
                on_session_start=on_session_start,
            )
            async with rio.testing.BrowserClient(app) as test_client:
                await asyncio.sleep(UI_SETTLE_S)

                # Edit Alice, accept -- do NOT save yet.
                await _edit_weight_lbs(test_client, 'Trackchangesalice|Trackchangesaliceln', '222.5')
                assert set(ce.stocker.change_trackers) == {alice}
                assert alice.weight_lbs == 150.0, 'accepting the dialog must not export the tracked edit'

                # Switch to Bob, edit him too, accept -- still no save for either.
                await _edit_weight_lbs(test_client, 'Trackchangesbob|Trackchangesbobln', '155.5')
                assert set(ce.stocker.change_trackers) == {alice, bob}
                assert bob.weight_lbs == 200.0
                assert alice.weight_lbs == 150.0, 'Alice edit must still be isolated after editing Bob'

                # Switch back to Alice and save her -- "saving after returning".
                await _select_entity(test_client, 'Trackchangesalice|Trackchangesaliceln')
                await _click_save(test_client)

                assert set(ce.stocker.change_trackers) == {bob}, 'only Alice must be cleared after her save'
                saved_alice = Person.collection().load(alice.id().value)
                assert saved_alice['weight_lbs'] == 222.5
                saved_bob = Person.collection().load(bob.id().value)
                assert saved_bob['weight_lbs'] == 200.0, 'Bob must remain unsaved/pending in the store'

                # Now save Bob too.
                await _select_entity(test_client, 'Trackchangesbob|Trackchangesbobln')
                await _click_save(test_client)

                assert ce.stocker.change_trackers == {}
                saved_bob = Person.collection().load(bob.id().value)
                assert saved_bob['weight_lbs'] == 155.5

                searchable_list = ce.searchable_list
                test_client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

            wr = weakref.ref(ce)
            del ce
            gc.collect()
            assert wr() is not None, 'select_hook must keep CollectionEditor reachable via the widget tree'

            searchable_list.release()
            if widget is not None:
                widget.component = None
                widget.subcomponent = None
            widget = None
            del searchable_list
        finally:
            alice.delete()
            bob.delete()


async def test_collection_editor_new_and_delete_entity(monkeypatch, ts_instance) -> None:  # noqa: F811
    """The two CollectionEditor paths the tests above never touch, end-to-end:

    ``on_new_entity`` -- 'New' opens the entity dialog whose Ok is 'Save' (save=True),
    so accepting it persists the entity and ``accept_hook`` lists it via ``add_choice``;
    and ``EntityStocker.on_delete_entity`` -> ``CollectionEditor.on_deleted_entity`` --
    'delete' asks for confirmation, and only 'Yes' deletes the entity, drops its row and
    clears the right pane.  Declining ('No') must leave all three untouched.

    Backed by a real ``ts_instance`` store (not ``CACHE_ONLY`` ``mock_db_ops``) since
    both paths round-trip through it.  ``load_ids`` returns nothing so the created
    entity is the only row, and its ID doubles as the list label and the store ``_id``.
    """
    with ts_instance, INTERACTIVE():
        monkeypatch.setattr(Person, 'load_ids', list)  # list() == [] -- nothing listed up front
        row = 'Newentityfirst|Newentitylast'

        try:
            ce: CollectionEditor | None = None
            widget = None

            def on_session_start(session):
                nonlocal ce, widget
                ctx = UserSessionContext()
                ctx.interactive = BTP.current()
                session.attach(ctx)
                with session_context(session):
                    ce = CollectionEditor(coll=Collection(cls=Person))
                    widget = ce.main_widget()

            app = rio.App(
                name='collection_editor_new_delete_test',
                build=lambda: DynamicComponent(widget),
                on_session_start=on_session_start,
            )
            async with rio.testing.BrowserClient(app) as test_client:
                await asyncio.sleep(UI_SETTLE_S)

                await _press_named_button(test_client, 'New')
                await wait_for_dialog_button(test_client, 'Save', timeout_ms=_CE_TIMEOUT)
                await asyncio.sleep(UI_SETTLE_S)

                # Same fixed-field-order reasoning as _edit_weight_lbs, but the New
                # dialog is the only input after the left pane's search box (index 0):
                # 1/2 = the ID traits, 3 = dob, 4 = weight_lbs.
                await _set_input_value(test_client, 1, 'Newentityfirst')
                await _set_input_value(test_client, 2, 'Newentitylast')
                await _set_input_value(test_client, 4, '165.5')

                await _press_named_button(test_client, 'Save')
                await wait_for_selectable_item_text(test_client, row, timeout_ms=_CE_TIMEOUT)

                stored = Person.collection().load(row)
                assert stored is not None, 'Save must persist the new entity'
                assert stored['weight_lbs'] == 165.5, 'dialog edits must reach the saved entity'

                await _select_entity(test_client, row)
                assert ce.current_entity is not None
                assert ce.current_entity.id().value == row

                # Declined confirmation: nothing is deleted.
                await _press_named_button(test_client, 'delete')
                await wait_for_dialog_button(test_client, 'No', timeout_ms=_CE_TIMEOUT)
                await asyncio.sleep(UI_SETTLE_S)
                await _press_named_button(test_client, 'No')

                assert Person.collection().load(row) is not None, 'declining must not delete'
                await wait_for_selectable_item_text(test_client, row, timeout_ms=_CE_TIMEOUT)

                await _press_named_button(test_client, 'delete')
                await wait_for_dialog_button(test_client, 'Yes', timeout_ms=_CE_TIMEOUT)
                await asyncio.sleep(UI_SETTLE_S)
                await _press_named_button(test_client, 'Yes')

                assert Person.collection().load(row) is None, 'confirmed delete must remove the entity'
                await wait_until(
                    lambda: test_client.execute_js(f'![...document.querySelectorAll(".rio-selectable-item")].some(el => el.innerText === "{row}")'),
                    timeout_s=10.0,
                    message='deleted entity to disappear from the list',
                )
                # on_deleted_entity also clears the right pane -- with no current entity
                # there is no stocker to press 'delete' on any more.
                await wait_until(
                    lambda: 'delete' not in {b.content for b in test_client.get_components(rio.Button)},
                    timeout_s=10.0,
                    message='stocker pane to be cleared after deletion',
                )

                searchable_list = ce.searchable_list
                test_client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

            wr = weakref.ref(ce)
            del ce
            gc.collect()
            assert wr() is not None, 'select_hook must keep CollectionEditor reachable via the widget tree'

            searchable_list.release()
            if widget is not None:
                widget.component = None
                widget.subcomponent = None
            widget = None
            del searchable_list
        finally:
            Person.collection().delete(row)  # no-op once the UI delete above succeeded
