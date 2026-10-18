"""Thin Streamlit demo for agent output delivery. All logic lives in
deliver/demo_helpers.py (stdlib, fully tested); this file only renders."""

import tempfile

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("pip install streamlit, then run: streamlit run demo/app.py")

from deliver.channels import FakeSMTP
from deliver.demo_helpers import deliver_all, sample_result

st.title("Agent output delivery")
result = sample_result()
st.subheader(result.title)
st.write(result.summary)

if st.button("Deliver to all four channels"):
    tmp = tempfile.mkdtemp()
    out = deliver_all(result, f"{tmp}/feed.db", f"{tmp}/reports",
                      smtp_factory=FakeSMTP)
    for name, receipt in out["receipts"].items():
        st.success(f"{name}: delivered at {receipt.delivered_at}")
    st.write("Audit chain verified:", out["audit"].verify())
    st.code(out["receipts"]["chat"].detail["message"][:600])
