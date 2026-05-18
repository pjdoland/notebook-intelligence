// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, { useId, useState } from 'react';

export function AskUserQuestion(props: any) {
  const userQuestions = props.userQuestions.content;
  const [selectedAnswers, setSelectedAnswers] = useState<{
    [key: string]: string[];
  }>({});

  // Form-scoped id prefix so DOM ids stay unique even when two questions
  // share label text (or several AskUserQuestion forms render in the
  // same chat transcript). React.useId() is the purpose-built primitive
  // here: stable for the component's lifetime, SSR-safe, and survives
  // StrictMode double-render without producing mismatched id/htmlFor
  // pairs (a Math.random fallback could mis-pair under cache eviction).
  // The server-provided identifier is preferred when present so two
  // remounts of the same form keep the same DOM ids.
  const reactId = useId();
  const serverId = userQuestions.identifier?.id;
  const formIdPrefix =
    typeof serverId === 'string' && serverId.length > 0
      ? `nbi-auq-${serverId}`
      : `nbi-auq${reactId}`;

  const onOptionSelected = (question: any, option: any) => {
    if (question.multiSelect) {
      if (selectedAnswers[question.question]?.includes(option.label)) {
        setSelectedAnswers({
          ...selectedAnswers,
          [question.question]: (
            selectedAnswers[question.question] ?? []
          ).filter((o: any) => o !== option.label)
        });
      } else {
        setSelectedAnswers({
          ...selectedAnswers,
          [question.question]: [
            ...(selectedAnswers[question.question] ?? []),
            option.label
          ]
        });
      }
    } else {
      setSelectedAnswers({
        ...selectedAnswers,
        [question.question]: [option.label]
      });
    }
  };

  return (
    <>
      {userQuestions.title ? (
        <div>
          <b>{userQuestions.title}</b>
        </div>
      ) : null}
      {userQuestions.message ? <div>{userQuestions.message}</div> : null}
      <form
        className="ask-user-question-form"
        onSubmit={event => {
          event.preventDefault();
          props.onSubmit(selectedAnswers);
        }}
      >
        {userQuestions.questions.map((question: any, qIndex: number) => {
          const questionDomId = `${formIdPrefix}-q${qIndex}`;
          // A single-select group is a radio group with a shared name so
          // screen readers announce "1 of N selected" rather than
          // treating each option as an independent checkbox. The wrapper
          // role mirrors the input type: radiogroup for radios, group
          // (the ARIA-1.2 fallback when no dedicated checkbox-group role
          // exists) for checkboxes.
          const inputType = question.multiSelect ? 'checkbox' : 'radio';
          const groupRole = question.multiSelect ? 'group' : 'radiogroup';
          return (
            <div
              className="ask-user-question-container"
              key={questionDomId}
              role={groupRole}
              aria-labelledby={`${questionDomId}-label`}
            >
              <div
                className="ask-user-question-question"
                id={`${questionDomId}-label`}
              >
                {question.question}
              </div>
              <div className="ask-user-question-header">{question.header}</div>
              <div className="ask-user-question-options">
                {question.options.map((option: any, oIndex: number) => {
                  const optionDomId = `${questionDomId}-o${oIndex}`;
                  return (
                    <div className="ask-user-question-option" key={optionDomId}>
                      <div className="ask-user-question-option-input-container">
                        <input
                          id={optionDomId}
                          name={questionDomId}
                          type={inputType}
                          checked={
                            selectedAnswers[question.question]?.includes(
                              option.label
                            ) ?? false
                          }
                          onChange={() => onOptionSelected(question, option)}
                        />
                        <label
                          htmlFor={optionDomId}
                          className="ask-user-question-option-label-container"
                        >
                          <div className="ask-user-question-option-label">
                            {option.label}
                          </div>
                          <div className="ask-user-question-option-description">
                            {option.description}
                          </div>
                        </label>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        <div className="ask-user-question-footer">
          <button
            type="submit"
            className="jp-Dialog-button jp-mod-accept jp-mod-styled"
          >
            <div className="jp-Dialog-buttonLabel">
              {userQuestions.submitLabel}
            </div>
          </button>
          <button
            type="button"
            className="jp-Dialog-button jp-mod-reject jp-mod-styled"
            onClick={() => {
              props.onCancel();
            }}
          >
            <div className="jp-Dialog-buttonLabel">
              {userQuestions.cancelLabel}
            </div>
          </button>
        </div>
      </form>
    </>
  );
}
