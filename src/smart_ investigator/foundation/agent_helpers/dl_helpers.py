"""Helper functions for Decline Letter agent integration with Master Agent streaming."""

from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent
)
from mlflow.types.responses_helpers import (
    OutputItem, Content, Response, ResponseOutputItemDoneEvent,
    ResponseErrorEvent, ResponseCompletedEvent, ResponseTextDeltaEvent
)
from uuid import uuid4


def convert_dl_response_to_event_stream(response: ResponsesAgentResponse):
    """
    Map DL agent's ResponsesAgentResponse to an iterator of ResponsesAgentStreamEvent
    to mimic streaming for the master agent.
    """
    # response.output[0] is an OutputItem already
    response_item = response.output[0]

    # Extract the content from the output item
    response_content = response_item.content[0]

    # Pull routing info safely from custom_outputs.entries
    entries = response.custom_outputs.get('entries', {})
    next_node = entries.get('next_node')
    is_interrupt = bool(next_node)
    state_values = entries.get('state_values')
    form_outputs_dl = entries.get('form_outputs_dl')

    # Inject custom outputs on the content object
    response_content.custom_outputs = dict(
        artifact=form_outputs_dl if form_outputs_dl is not None else [],
        agent_name="Decline_letter_agent"
    )

    # First streamed event: output item done
    response_event = ResponsesAgentStreamEvent(
        type="response.output_item.done",
        item=OutputItem(
            type="message",
            id=str(uuid4()),
            content=[response_content],
            custom_outputs=dict(
                event="response",
                state_values=state_values,
                is_interrupt=is_interrupt
            ),
        ),
    )

    # Second streamed event: completed + state
    complete_event = ResponsesAgentStreamEvent(
        type="response.completed",
        response=Response(
            output=[],
            metadata={
                'state': entries.get('state'),
                'next_node': next_node if next_node else ''
            }
        ),
        status="completed",
    )

    for event in [response_event, complete_event]:
        yield event
