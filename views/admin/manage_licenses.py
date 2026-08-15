"""

AI Habit Tracker SaaS - License Key Management
Admin dashboard for generating, viewing, searching, filtering, and revoking license keys.

"""

import math
from datetime import datetime
from typing import List, Dict, Any

import streamlit as st
from auth import auth
import ui_components
import utils
from services.license_service import (
    bulk_create_licenses, export_keys_csv, get_license_counts,
    get_licenses_paginated, revoke_license, reinstate_license
)


def init_session_state() -> None:
    if "license_page" not in st.session_state:
        st.session_state.license_page = 1
    if "generated_keys" not in st.session_state:
        st.session_state.generated_keys = None


def render_counts() -> None:
    counts = get_license_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Keys", f"{counts['total']:,}")
    c2.metric("Unused", f"{counts['unused']:,}")
    c3.metric("Active", f"{counts['active']:,}")
    c4.metric("Revoked", f"{counts['revoked']:,}")


def render_generate_section() -> None:
    st.subheader("🔑 Generate License Keys")
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            count = st.number_input("Number of keys to generate", min_value=1,
                                    max_value=1000, value=5, key="gen_count")
        with col2:
            st.write("")
            st.write("")
            if st.button("⚡ Generate Keys", type="primary", use_container_width=True,
                         key="btn_generate"):
                with st.spinner(f"Generating {count} license keys..."):
                    success, msg, keys = bulk_create_licenses(count)
                if success:
                    st.session_state.generated_keys = keys
                    st.success(msg)
                    get_license_counts.clear()
                    get_licenses_paginated.clear()
                    st.rerun()
                else:
                    st.error(msg)

        if st.session_state.generated_keys:
            keys = st.session_state.generated_keys
            st.divider()
            st.markdown(f"**{len(keys)} keys generated** — Download or copy below:")
            csv_data = export_keys_csv(keys)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"license_keys_{utils.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
                key="btn_download_csv"
            )
            with st.expander("View generated keys"):
                st.code("\n".join(keys), language=None)


def render_licenses_table() -> None:
    st.subheader("📋 All License Keys")

    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("🔍 Search by key or email", placeholder="HT-... or user@email.com", key="lic_search")
    with col2:
        status_filter = st.selectbox("Status Filter", ["All", "Unused", "Active", "Revoked"],
                                     key="lic_status_filter")

    per_page = 20
    page = st.session_state.license_page
    licenses, total = get_licenses_paginated(page, per_page, status_filter, search)
    total_pages = math.ceil(total / per_page) if total > 0 else 1

    if page > total_pages:
        st.session_state.license_page = total_pages
        page = total_pages

    st.caption(f"Showing page {page} of {total_pages} ({total:,} total records)")

    if not licenses:
        ui_components.render_empty_state("🔑", "No licenses found",
                                         "Generate keys or adjust your filters.")
        return

    for lic in licenses:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1.5, 2.5, 1.5])
            with c1:
                st.code(lic["license_key"], language=None)
                if lic.get("created_at"):
                    st.caption(f"Created: {utils.format_date(lic['created_at'])}")
            with c2:
                status = lic.get("status", "unused")
                if status == "active":
                    st.markdown(ui_components.render_badge("ACTIVE", "active"),
                                unsafe_allow_html=True)
                elif status == "unused":
                    st.markdown(ui_components.render_badge("UNUSED", "primary"),
                                unsafe_allow_html=True)
                else:
                    st.markdown(ui_components.render_badge("REVOKED", "danger"),
                                unsafe_allow_html=True)
            with c3:
                assigned_email = lic.get("assigned_email")
                profile_data = lic.get("profiles")
                display_name = profile_data.get("display_name") if isinstance(profile_data, dict) else None

                if assigned_email:
                    st.markdown(f"**Email:** `{assigned_email}`")
                elif display_name:
                    st.markdown(f"**User:** {display_name}")
                else:
                    st.caption("Unassigned")

                if lic.get("activated_at"):
                    st.caption(f"Activated: {utils.format_date(lic['activated_at'])}")
                elif lic.get("revoked_at"):
                    st.caption(f"Revoked: {utils.format_date(lic['revoked_at'])}")
            with c4:
                status = lic.get("status", "unused")
                if status in ("active", "unused"):
                    if st.button("Revoke", key=f"rev_{lic['id']}", use_container_width=True):
                        ok, msg = revoke_license(lic["id"])
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                elif status == "revoked":
                    if st.button("Reinstate", key=f"rein_{lic['id']}",
                                 use_container_width=True):
                        ok, msg = reinstate_license(lic["id"])
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    # Pagination
    if total_pages > 1:
        st.write("")
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("⬅️ Prev", disabled=(page <= 1), key="lic_prev",
                         use_container_width=True):
                st.session_state.license_page -= 1
                st.rerun()
        with p2:
            st.markdown(f"<div style='text-align:center; padding-top:0.5rem;'>"
                        f"Page <b>{page}</b> of {total_pages}</div>",
                        unsafe_allow_html=True)
        with p3:
            if st.button("Next ➡️", disabled=(page >= total_pages), key="lic_next",
                         use_container_width=True):
                st.session_state.license_page += 1
                st.rerun()


def main() -> None:
    auth.require_admin()
    init_session_state()

    ui_components.render_hero("🔑 License Management",
                              "Generate, track, filter, and manage customer license keys.",
                              icon="🔑")

    render_counts()
    st.write("")
    render_generate_section()
    st.write("")
    render_licenses_table()


if __name__ == "__main__":
    main()
