# Intelligent Stack Overflow Query Agent

This project implements an intelligent agent framework designed to interactively query Stack Overflow for programming questions and retrieve refined answers. It uses a combination of large language models (LLMs) and external tools for search and summarization, orchestrated through a state machine graph architecture using LangGraph.

---

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [Components](#components)
- [Extending the Agent](#extending-the-agent)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

This agent is built around a core LLM model bound to multiple tools that provide specialized functions such as fetching relevant URLs from Stack Overflow, extracting question and answer content, and summarizing responses.

Using a graph-based state machine (LangGraph), the agent dynamically switches between:

* **Querying the LLM**
* **Calling external tools**
* **Refining ambiguous or incomplete questions**
* **Refining and validating answers**

This design enables an iterative, multi-step approach to delivering accurate and relevant programming help.

---

## Features

* **Multi-tool integration**: Supports multiple external tools including URL retrieval and answer summarization.
* **State graph orchestration**: Uses LangGraph to define and compile a state machine workflow.
* **Iterative refinement**: Dynamically refines user queries and agent answers for improved quality.
* **Conditional branching**: Makes decisions based on tool responses to continue or stop the workflow.
* **Groq LLM support**: Uses the Groq-powered ChatGroq LLM backend for natural language understanding and generation.

---

## Architecture

The agent architecture is based on a directed graph representing states and transitions, with nodes representing:

* **LLM query processing** (`llm` node)
* **Tool invocations** (one node per tool)
* **Question refinement node** (`refine_question`)
* **Answer refinement node** (`refine_answer`)

Transitions depend on results, such as whether relevant Stack Overflow results are found or if answers need more refinement.

---

## Installation

1.  **Clone this repository**:

    ```bash
    git clone [https://github.com/yourusername/stack-overflow-agent.git](https://github.com/yourusername/stack-overflow-agent.git)
    cd stack-overflow-agent
    ```

2.  **Install required Python packages** (example):

    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment variables** by creating a `.env` file in the root:

    ```ini
    GROQ_API_KEY=your_groq_api_key_here
    ```

    Ensure you have access to the Groq LLM and the required tools (`StackOverflow`, `get_urls`, and `summarizer` modules).

---

## Usage

Here is a simple usage example:

```python
from langchain_groq import ChatGroq
from your_agent_module import Agent, get_url_tool, Stack_overflow_tool, StackOverflowSummarizer
from langchain_core.messages import HumanMessage

model = ChatGroq(model="llama-3.3-70b-versatile")
agent = Agent(model, [get_url_tool, Stack_overflow_tool, StackOverflowSummarizer], system="You are a helpful assistant")

messages = HumanMessage(content="How to reverse a string in Python?")
for event in agent.graph.stream({"messages": messages}):
    print(event)