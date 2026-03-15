"""Tests for Bayesian probability estimation."""

import pytest
from lib.bayesian import BayesianEstimator

class TestBayesianEstimator:
    def test_posterior_with_equal_prior_returns_equal(self):
        """When prior=0.5 and likelihood=0.5, posterior should be 0.5."""
        estimator = BayesianEstimator(base_prior=0.5)
        posterior = estimator.calculate_posterior(
            p_prior=0.5,
            likelihood_up=0.5,
            likelihood_down=0.5
        )
        assert abs(posterior - 0.5) < 0.001

    def test_posterior_with_skewed_likelihood(self):
        """Order book skew should shift probability."""
        estimator = BayesianEstimator(base_prior=0.5)
        posterior = estimator.calculate_posterior(
            p_prior=0.5,
            likelihood_up=0.7,
            likelihood_down=0.3
        )
        assert posterior > 0.5
        assert posterior < 1.0

    def test_posterior_respects_memory_modifier(self):
        """Memory feedback should adjust prior."""
        estimator = BayesianEstimator(base_prior=0.5, memory_modifier=0.1)
        p_prior = estimator.adjust_prior_with_memory()
        assert abs(p_prior - 0.6) < 0.001

    def test_posterior_clamps_to_valid_range(self):
        """Posterior must stay in [0.01, 0.99]."""
        estimator = BayesianEstimator(base_prior=0.5)
        posterior = estimator.calculate_posterior(
            p_prior=0.99,
            likelihood_up=0.99,
            likelihood_down=0.01
        )
        assert posterior <= 0.99
        assert posterior >= 0.01

    def test_edge_calculation(self):
        """Edge is posterior minus market price."""
        estimator = BayesianEstimator(base_prior=0.5)
        edge = estimator.calculate_edge(p_posterior=0.60, q_market=0.50)
        assert abs(edge - 0.10) < 0.001

    def test_edge_filter_blocks_insufficient_edge(self):
        """Edge below 3.5% threshold should block execution."""
        estimator = BayesianEstimator(base_prior=0.5, edge_threshold=0.035)
        assert not estimator.should_trade(edge=0.03)
        assert estimator.should_trade(edge=0.04)

    def test_order_book_skew_calculation(self):
        """Skew from L2 order book volumes."""
        estimator = BayesianEstimator(base_prior=0.5)
        order_book = {
            "bids": [{"size": "100"}, {"size": "50"}, {"size": "25"}],
            "asks": [{"size": "30"}, {"size": "20"}, {"size": "10"}]
        }
        skew = estimator.calculate_order_book_skew(order_book)
        assert skew > 0.5

    def test_likelihood_from_order_book(self):
        """Likelihood derived from order book skew."""
        estimator = BayesianEstimator(base_prior=0.5)
        order_book = {
            "bids": [{"size": "100"}, {"size": "50"}],
            "asks": [{"size": "30"}, {"size": "20"}]
        }
        likelihood_up, likelihood_down = estimator.likelihood_from_order_book(order_book)
        assert likelihood_up > likelihood_down
        assert likelihood_up + likelihood_down > 0