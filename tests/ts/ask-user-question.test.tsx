// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { AskUserQuestion } from '../../src/components/ask-user-question';

function makeProps(opts: {
  multiSelect: boolean;
  questions: { question: string; options: { label: string }[] }[];
  identifierId?: string;
  onSubmit?: jest.Mock;
}) {
  return {
    userQuestions: {
      content: {
        identifier: { id: opts.identifierId ?? 'form-1', callback_id: 'cb-1' },
        title: '',
        message: '',
        submitLabel: 'Submit',
        cancelLabel: 'Cancel',
        questions: opts.questions.map(q => ({
          question: q.question,
          header: '',
          multiSelect: opts.multiSelect,
          options: q.options.map(o => ({ label: o.label, description: '' }))
        }))
      }
    },
    onSubmit: opts.onSubmit ?? jest.fn(),
    onCancel: jest.fn()
  };
}

describe('AskUserQuestion', () => {
  it('renders type=radio inputs when multiSelect is false', () => {
    render(
      <AskUserQuestion
        {...makeProps({
          multiSelect: false,
          questions: [
            { question: 'Pick one', options: [{ label: 'A' }, { label: 'B' }] }
          ]
        })}
      />
    );
    const inputs = screen.getAllByRole('radio');
    expect(inputs).toHaveLength(2);
    // Both share a name attribute so they form a native radio group.
    expect(inputs[0].getAttribute('name')).toBe(inputs[1].getAttribute('name'));
    // And no checkbox markup is rendered for this single-select question.
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('renders type=checkbox inputs when multiSelect is true', () => {
    render(
      <AskUserQuestion
        {...makeProps({
          multiSelect: true,
          questions: [
            { question: 'Pick any', options: [{ label: 'A' }, { label: 'B' }] }
          ]
        })}
      />
    );
    expect(screen.getAllByRole('checkbox')).toHaveLength(2);
    expect(screen.queryAllByRole('radio')).toHaveLength(0);
  });

  it('wraps single-select questions in role=radiogroup and multi-select in role=group', () => {
    render(
      <>
        <AskUserQuestion
          {...makeProps({
            multiSelect: false,
            questions: [
              { question: 'Single', options: [{ label: 'A' }, { label: 'B' }] }
            ],
            identifierId: 'form-single'
          })}
        />
        <AskUserQuestion
          {...makeProps({
            multiSelect: true,
            questions: [
              { question: 'Multi', options: [{ label: 'A' }, { label: 'B' }] }
            ],
            identifierId: 'form-multi'
          })}
        />
      </>
    );
    expect(screen.getByRole('radiogroup')).toHaveAccessibleName('Single');
    expect(screen.getByRole('group')).toHaveAccessibleName('Multi');
  });

  it('keeps duplicate option labels across two questions independent', () => {
    const onSubmit = jest.fn();
    render(
      <AskUserQuestion
        {...makeProps({
          multiSelect: false,
          identifierId: 'form-dup',
          questions: [
            { question: 'First', options: [{ label: 'Yes' }, { label: 'No' }] },
            { question: 'Second', options: [{ label: 'Yes' }, { label: 'No' }] }
          ],
          onSubmit
        })}
      />
    );
    // Click the first question's "Yes" by targeting the label associated
    // with the input via the form-scoped id. Querying by label text
    // alone would be ambiguous with the duplicate "Yes" in question 2.
    const radios = screen.getAllByRole('radio');
    // Order in the DOM: q0-o0 ("Yes" of First), q0-o1, q1-o0 ("Yes" of Second), q1-o1.
    fireEvent.click(radios[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.First).toEqual(['Yes']);
    // The second question's "Yes" must remain unselected (the DOM ids
    // are form-scoped so the click on the first did not cross-toggle).
    expect(submitted.Second).toBeUndefined();
    expect(radios[0]).toBeChecked();
    expect(radios[2]).not.toBeChecked();
  });

  it('replaces selection on a fresh single-select click', () => {
    const onSubmit = jest.fn();
    render(
      <AskUserQuestion
        {...makeProps({
          multiSelect: false,
          questions: [
            { question: 'Q', options: [{ label: 'A' }, { label: 'B' }] }
          ],
          onSubmit
        })}
      />
    );
    const [a, b] = screen.getAllByRole('radio');
    fireEvent.click(a);
    fireEvent.click(b);
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    expect(onSubmit.mock.calls[0][0]).toEqual({ Q: ['B'] });
  });

  it('accumulates selections in a multi-select question', () => {
    const onSubmit = jest.fn();
    render(
      <AskUserQuestion
        {...makeProps({
          multiSelect: true,
          questions: [
            { question: 'Q', options: [{ label: 'A' }, { label: 'B' }] }
          ],
          onSubmit
        })}
      />
    );
    const [a, b] = screen.getAllByRole('checkbox');
    fireEvent.click(a);
    fireEvent.click(b);
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    expect(onSubmit.mock.calls[0][0]).toEqual({ Q: ['A', 'B'] });
  });
});
