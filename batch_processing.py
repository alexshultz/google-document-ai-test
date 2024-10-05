"""
Makes a Batch Processing Request to Document AI
"""

import re

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import InternalServerError
from google.api_core.exceptions import RetryError
from google.cloud import documentai
from google.cloud import storage

# TODO(developer): Fill these variables before running the sample.
project_id = "documentai-hazel"
location = "us"  # Format is "us" or "eu"
test_processor_id = "c2bdedc9ee4057e7" # test-ocr-processor
vendor_processor_id = "b9f76489553029f6" # vendor-processor
processor_id = test_processor_id  # Create processor before running sample
gcs_output_uri = "gs://temp-pooh"  # Must end with a trailing slash `/`. Format: gs://bucket/directory/subdirectory/
# processor_version_id = (
#    "YOUR_PROCESSOR_VERSION_ID"  # Optional. Example: pretrained-ocr-v1.0-2020-09-23
#)

# TODO(developer): If `gcs_input_uri` is a single file, `mime_type` must be specified.
gcs_input_uri = "/Users/alex/Documents/github/google-document-ai-test/peter_graves_test.pdf"  # Format: `gs://bucket/directory/file.pdf` or `gs://bucket/directory/`
input_mime_type = "application/pdf"
field_mask = "text,entities,pages.pageNumber"  # Optional. The fields to return in the Document object.


def batch_process_documents(
    project_id: str,
    location: str,
    processor_id: str,
    gcs_input_uri: str,
    gcs_output_uri: str,
    processor_version_id: str = None,
    input_mime_type: str = None,
    field_mask: str = None,
    timeout: int = 400,
):
    # Initialize client options with API endpoint
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")

    # Create the Document AI processor client
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    # Configure input documents (single file or entire directory)
    if not gcs_input_uri.endswith("/") and "." in gcs_input_uri:
        gcs_document = documentai.GcsDocument(
            gcs_uri=gcs_input_uri, mime_type=input_mime_type
        )
        gcs_documents = documentai.GcsDocuments(documents=[gcs_document])
        input_config = documentai.BatchDocumentsInputConfig(gcs_documents=gcs_documents)
    else:
        gcs_prefix = documentai.GcsPrefix(gcs_uri_prefix=gcs_input_uri)
        input_config = documentai.BatchDocumentsInputConfig(gcs_prefix=gcs_prefix)

    # Set up output configuration
    gcs_output_config = documentai.DocumentOutputConfig.GcsOutputConfig(
        gcs_uri=gcs_output_uri, field_mask=field_mask
    )
    output_config = documentai.DocumentOutputConfig(gcs_output_config=gcs_output_config)

    # Define the processor version or processor name
    if processor_version_id:
        name = client.processor_version_path(
            project_id, location, processor_id, processor_version_id
        )
    else:
        name = client.processor_path(project_id, location, processor_id)

    # Create and send the batch process request
    request = documentai.BatchProcessRequest(
        name=name,
        input_documents=input_config,
        document_output_config=output_config,
    )

    # Start the batch process and wait for it to complete
    operation = client.batch_process_documents(request)
    try:
        print(f"Waiting for operation {operation.operation.name} to complete...")
        operation.result(timeout=timeout)
    except (RetryError, InternalServerError) as e:
        print(e.message)

    # Check the metadata to see if processing succeeded
    metadata = documentai.BatchProcessMetadata(operation.metadata)
    if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
        raise ValueError(f"Batch Process Failed: {metadata.state_message}")

    # Process the output files from the bucket
    storage_client = storage.Client()
    for process in list(metadata.individual_process_statuses):
        matches = re.match(r"gs://(.*?)/(.*)", process.output_gcs_destination)
        if not matches:
            print(
                "Could not parse output GCS destination:",
                process.output_gcs_destination,
            )
            continue

        output_bucket, output_prefix = matches.groups()
        output_blobs = storage_client.list_blobs(output_bucket, prefix=output_prefix)
        for blob in output_blobs:
            if blob.content_type != "application/json":
                print(f"Skipping non-supported file: {blob.name} - Mimetype: {blob.content_type}")
                continue

            # Print extracted text from the document
            document = documentai.Document.from_json(blob.download_as_bytes(), ignore_unknown_fields=True)
            print("The document contains the following text:")
            print(document.text)



if __name__ == "__main__":
    batch_process_documents(
        project_id=project_id,
        location=location,
        processor_id=processor_id,
        gcs_input_uri=gcs_input_uri,
        gcs_output_uri=gcs_output_uri,
        input_mime_type=input_mime_type,
        field_mask=field_mask,
    )
