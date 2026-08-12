# Automotive Lab Book Builder

Build a customized PDF lab booklet from individual lab sheets. The repository includes the original Tkinter desktop program and a Streamlit web version that instructors can use without installing Python.

## Web version features

- Upload multiple PDF lab sheets at once
- Arrange PDFs and place the table of contents anywhere in the booklet
- Keep cover pages before the TOC without listing them in the TOC
- Automatically create multi-page tables of contents
- Add page numbers
- Download the finished booklet directly from the browser

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Sign in at [share.streamlit.io](https://share.streamlit.io/) with GitHub.
2. Choose **Create app** and select this repository.
3. Set the branch to `main` and the main file path to `app.py`.
4. Deploy the app.

Streamlit will install the packages in `requirements.txt`. Updates pushed to the selected GitHub branch are redeployed automatically.

## Desktop version

`PDFcollator.py` is the original desktop version and remains available as a known-working baseline.
