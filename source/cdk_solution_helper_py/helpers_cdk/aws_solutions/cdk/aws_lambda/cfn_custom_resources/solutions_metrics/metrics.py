# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk.aws_lambda as lambda_

from pathlib import Path
from typing import Dict

from aws_cdk import (
    CfnResource,
    Fn,
    CfnCondition,
    Aws,
)
from constructs import Construct

from aws_solutions.cdk.aws_lambda.python.function import SolutionsPythonFunction
from aws_solutions.cdk.cfn_nag import add_cfn_nag_suppressions, CfnNagSuppression

from cdk_nag import NagSuppressions

class Metrics(Construct):
    """Used to track anonymous solution deployment metrics."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        metrics: Dict[str, str],
    ):
        super().__init__(scope, construct_id)

        if not isinstance(metrics, dict):
            raise ValueError("metrics must be a dictionary")

        self._metrics_function = SolutionsPythonFunction(
            self,
            "MetricsFunction",
            entrypoint=Path(__file__).parent
            / "src"
            / "custom_resources"
            / "metrics.py",
            function="handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
        )
        add_cfn_nag_suppressions(
            resource=self._metrics_function.node.default_child,
            suppressions=[
                CfnNagSuppression(
                    "W89", "This AWS Lambda Function is not deployed to a VPC"
                ),
                CfnNagSuppression(
                    "W92",
                    "This AWS Lambda Function does not require reserved concurrency",
                ),
            ],
        )

        self._send_anonymous_usage_data = CfnCondition(
            self,
            "SendAnonymizedData",
            expression=Fn.condition_equals(
                Fn.find_in_map("Solution", "Data", "SendAnonymizedData"), "Yes"
            ),
        )
        self._send_anonymous_usage_data.override_logical_id("SendAnonymizedData")

        properties = {
            "ServiceToken": self._metrics_function.function_arn,
            "Solution": self.node.try_get_context("SOLUTION_ID"),
            "Version": self.node.try_get_context("SOLUTION_VERSION"),
            "Region": Aws.REGION,
            **metrics,
        }
        self.solution_metrics = CfnResource(
            self,
            "SolutionMetricsAnonymousData",
            type="Custom::AnonymousData",
            properties=properties,
        )
        self.solution_metrics.override_logical_id("SolutionMetricsAnonymousData")
        self.solution_metrics.cfn_options.condition = self._send_anonymous_usage_data

        NagSuppressions.add_resource_suppressions(
            self._metrics_function.role,
            [
                {
                    "id": 'AwsSolutions-IAM5',
                    "reason": '* Resources will be suppred by cdk nag and it has to be not suppressed',
                    "appliesTo": ['Resource::arn:<AWS::Partition>:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/*']
                },
            ],
        )