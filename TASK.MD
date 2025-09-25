# Forgent Checklist (Next.js + FastAPI + Worker)

##Introduction

The goal of this test is to build a Checklist app that allows users to define a set of questions and conditions related to public tender documents, upload multiple tender documents, and finally, automatically fill out the checklist with answers to the questions and evaluations of the conditions based on the uploaded documents.
The purpose of the checklist app to allow companies to make quick decisions about whether a given public tender is a good fit for them.
You will be working with a provided set of documents and will need to ensure your system can accurately extract and evaluate the required information.
The system should leverage the Anthropic API (or any other one if you bring your own API key) for language processing and a suitable mechanism for efficient content storage and retrieval, and for evaluating conditions. Please use either Javascript/Typescript or Python (or both) for the implementation in at least one parts of the stack (frontend, backend, or both); For example, you could produce a frontend in Javascript and a backend in any language of your choice, or a backend in Python and a frontend in any language of your choice. We just want to ensure you use at least one of the languages we use at Forgent AI.
We are looking for a well-structured, functional solution with clear documentation and efficient error handling. Your ability to extract relevant information, answer specific questions, and evaluate conditions accurately will be key evaluation criteria.

## Test details

### Product Specification

Checklist app for public tender documents
Objective
Develop a Document Checklist System that enables users to:
Define a set of questions they want answered from tender documents (e.g., "In what form should offers/applications be submitted?" or “When is the due date for the tender?”).
Define conditions (i.e. questions that can be answered by true or false only) that they want evaluated from tender documents (e.g., "Is the application deadline before 31.12.2025?").
Upload multiple tender documents.
Automatically fill out the checklist displaying the questions with answers and the evaluation (true/false) of the conditions, based on the uploaded documents
You are provided with three files to feed into the system for testing. Please ensure the system is working for these documents and the below example questions and conditions. Also verify that the generated checklist is displayed correctly within the app. We will use your code to validate the output on these.

### Example questions

'In welcher Form sind die Angebote/Teilnahmeanträge einzureichen?' (In what form should offers/applications be submitted?)
'Wann ist die Frist für die Einreichung von Bieterfragen?' (When is the deadline for submitting bidder questions?)

### Example conditions

'Ist die Abgabefrist vor dem 31.12.2025?' (Is the application deadline before 31.12.2025?)
Functional requirements
Document Ingestion:
Users must be able to upload PDF documents. The files are all in the same 'data' folder. Please create a database to store the user’s files.
The user can see which files are uploaded and used for the checklist.
The system must extract and process content from these documents for information extraction. Please use Anthropic’s file api to upload the files into the model. These files can the be directly ingested by the models, i.e. they are added to the model context so it can answer questions about it. Other model providers offer similar APIs (e.g. Google also offers a file API).

## Functional requirements

1. **Document Ingestion:**
   - Users must be able to upload PDF documents. The files are all in the same 'data' folder. Please create a database to store the user’s files.
   - The user can see which files are uploaded and used for the checklist.
   - The system must extract and process content from these documents for information extraction. Please use Anthropic’s file api to upload the files into the model. These files can the be directly ingested by the models, i.e. they are added to the model context so it can answer questions about it. Other model providers offer similar APIs (e.g. Google also offers a file API).
2. **Question & Condition Definition:**
   - The user can input and create and/or modify a default set of questions and conditions.
   - The system should be able to interpret and process these user-defined questions and conditions, i.e. the user can create a checklist.
3. **Information Extraction & Evaluation:**
   - Answers for the user queries are extracted and the conditions evaluated using LLMs (e.g. via the Claude API using the API key provided below) and information retrieved from the input documents.
   - Optimize the parameters to ensure correct answers and evaluations for the example questions and conditions (above - see Objective).

### Technical stack

- **Programming language**

  - One of the either Javascript/Typescript or Python (or both) should be used in one parts of the stack (frontend, backend, or both); For example, you could produce a frontend in Javascript and a backend in any language of your choice, or a backend in Python and a frontend in any language of your choice

- **API Keys**
  - Anthropic **API key** that can be used for LLM calls:
    ```jsx
    sk -
      ant -
      api03 -
      JhTc_82ogo1Srb53OxZcSYlpyw2pwENmDYxFT80_YHAHgMxxodSRwQr3ZRitWnRYzY2Ovoxqfmjd295mr7_cAg -
      s4416gAA;
    ```
    (NB: the API key will be deleted after the test, but nevertheless please do not share it)
  - You may use any other model of your choice but will then need to bring your own API keys

### Assumptions

- The system will be deployed in a controlled environment with the required computational resources and fast internet access.

## Summary deliverables

- Functional solution as described above.
- Source code hosted e.g. in a GitHub repository.
- Setup guide to install / deploy the system locally (including a minimal README).
- Documentation, ideally including:
  - Requirements and installation files.
  - Setup and installation guide.
  - Screenshots showing the checklist results displayed within the app for the 4 example questions and conditions. (mentioned above)

## Evaluation criteria

- Function / output (accuracy of answers and condition evaluations).
- Code quality incl. error handling and documentation.
- User interface usability.
- System performance and responsiveness.
