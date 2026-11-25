# Remaining Useful Life Prediction for Aircraft Engines: A Comparative Study with Explainable AI and Uncertainty Estimation

*Draft, 13 November 2026. All results are produced by the notebooks in this repository; the notebook that produces each table is named beneath it.*

> **A note on the title.** The working title was "Deep Learning-Based Remaining Useful Life Prediction…". It has been changed because the study did not find deep learning to be the best-performing approach, and the title should not suggest otherwise.

## Abstract

We study remaining useful life (RUL) prediction on the NASA C-MAPSS turbofan benchmark with attention to three questions that are often under-reported: how results are validated, how much they vary, and how far a prediction can be trusted. On the FD001 subset we compare linear regression, random forest and gradient-boosted trees on engineered features against four neural networks (MLP, LSTM, GRU, TCN) on 30-cycle sensor windows, using engine-wise validation and multiple random seeds. Tree models reach a test RMSE of 13.9 (random forest) and 14.8 ± 0.3 (XGBoost); three-seed ensembles of the neural networks reach 15.8 to 16.4. The networks appeared better on held-out training engines (10.4 to 11.4 against 12.8), an advantage that did not carry over to the test set. A single feature family, each sensor's change from the engine's own early-life level, accounts for most of the accuracy: removing it costs 3.7 cycles, removing any other family under 0.4. We show that validating on random rows instead of whole engines understates error by 34%. SHAP analysis of the boosted model identifies sensors consistent with the strongest trends in the raw data. Conformalized quantile regression gives 90% prediction intervals with 95% empirical coverage on FD001 and 87 to 92% on the other three subsets, but coverage for engines within 30 cycles of failure falls to 76% on FD004. With per-regime normalisation the same pipeline reaches a cross-validated RMSE of 12 to 14 cycles on all four subsets; across subsets, an unseen fault mode degrades a model far more than an unseen operating condition. The study uses simulated data only.

## 1. Introduction

Unplanned engine removals are costly, and maintenance at fixed intervals discards useful life from engines that wear slowly while being too late for those that wear quickly. Predicting an engine's remaining useful life from its sensor data is therefore a long-standing goal of prognostics and health management.

The C-MAPSS dataset [1] has become the standard benchmark for this problem, and a large literature reports steadily improving scores on it, increasingly with deep neural networks [2–4]. Three practical difficulties stand between such scores and a usable system. First, a score depends heavily on evaluation choices (how validation data are held out, whether the target is capped, whether the test truth is capped) that are not always stated. Second, a single number says nothing about how sure the model is. Third, a maintenance engineer needs to know why a prediction was made.

This paper reports a study designed around those difficulties. Its contributions are empirical and modest:

1. A like-for-like comparison of traditional and deep models on FD001 with engine-wise validation, several seeds, and the test set reserved for final scoring.
2. A measurement of how much common evaluation shortcuts change the reported error.
3. An ablation showing which engineered features carry the accuracy.
4. Explanations of the selected model and a check of their stability and plausibility.
5. Prediction intervals with measured coverage, including where coverage fails.
6. An assessment of generalisation to FD002–FD004 and of transfer between subsets.

We make no claim of state-of-the-art accuracy. The value of the study lies in what is measured and reported around the accuracy figures.

## 2. Related Work

Saxena et al. [1] introduced the C-MAPSS run-to-failure simulations and the asymmetric scoring function that penalises late predictions more heavily than early ones. Heimes [2] applied recurrent neural networks to the associated PHM08 challenge data, and work from that period established the practice, followed here, of limiting the RUL target to a constant during early life, on the argument that degradation is not observable until a fault has developed. Zheng et al. [3] applied LSTM networks to RUL estimation on C-MAPSS and other datasets. Li et al. [4] used deep convolutional networks on time windows of normalised raw sensor data without hand-crafted features. Recurrent architectures in this line of work build on the LSTM [5] and GRU [6]; temporal convolutional networks [7] and attention-based Transformers [8] have since been applied to sequence problems generally.

For tabular data, random forests [9] and gradient-boosted trees such as XGBoost [10] remain strong baselines. SHAP [11] attributes an individual prediction to input features using Shapley values. Conformal prediction provides distribution-free prediction intervals; conformalized quantile regression [12] combines it with quantile regression so that interval width adapts to the input. Hyperparameters in this study are searched with Optuna [13].

We deliberately do not tabulate RMSE values from prior work beside ours. Published results on C-MAPSS differ in the RUL cap, in whether the test truth is capped, in window length and in validation procedure, and Section 6.6 shows that one of these choices alone changes our own FD002 result from 12.8 to 25.0.

## 3. Dataset

C-MAPSS [1] contains four subsets of simulated turbofan run-to-failure trajectories (Table 1). Each row records one engine during one operating cycle: three operational settings and 21 sensor measurements. Training engines are recorded until failure. Test engines are truncated at an arbitrary point before failure, and the true RUL at that point is supplied separately.

**Table 1. The four subsets (measured from the files).**

| Subset | Operating conditions | Fault modes | Train engines | Test engines | Train rows |
|---|---:|---:|---:|---:|---:|
| FD001 | 1 | 1 (HPC) | 100 | 100 | 20,631 |
| FD002 | 6 | 1 (HPC) | 260 | 259 | 53,759 |
| FD003 | 1 | 2 (HPC, fan) | 100 | 100 | 24,720 |
| FD004 | 6 | 2 (HPC, fan) | 249 | 248 | 61,249 |

*Source: `docs/DATASET_INVENTORY.md`. The dataset's README lists FD004 as 248 training and 249 test trajectories; the files contain 249 and 248.*

In FD001 there are no missing values or duplicate rows. Engine lifetimes range from 128 to 362 cycles (median 199). Six sensors are constant and a seventh takes two adjacent values, leaving 14 informative sensors. Sensor noise in early life is close to Gaussian and nearly uncorrelated between sensors (largest pairwise correlation 0.06), while 28–86% of early-life variance, depending on the sensor, is due to differences between engines. A single principal component holds 64% of the variance of the 14 standardised sensors and has a Spearman correlation of −0.76 with RUL. Averaged over the fleet, an individual sensor departs from its healthy level by one noise standard deviation only in roughly the last 70–110 cycles.

## 4. Methodology

### 4.1 Validation protocol

All model selection uses the training set only, split by **whole engine**: 5-fold grouped cross-validation for tabular models and a fixed hold-out of 20 engines (seed 42) for early stopping of neural networks. The test set is used once per reported configuration and never to select a setting. Scalers and normalisation statistics are fitted on training engines only.

### 4.2 Target

The training target is RUL capped at 125 cycles. The cap was chosen on FD001 by cross-validation against the uncapped truth on fixed sets of rows (Section 6.1). Predictions are clipped to [0, 125]. Unless stated otherwise, test metrics are computed against the true RUL as supplied, which reaches 145 in FD001 and about 195 in FD002 and FD004.

### 4.3 Features for tabular models

For each of the 14 sensors: the current reading, its rolling mean and standard deviation over the last 30 cycles, and its difference from the engine's own mean over its first 20 cycles (56 features). All features are causal: a value at cycle *t* uses cycles 1 to *t* of the same engine only. Engine age is not used as a feature.

### 4.4 Models

*Tabular:* linear regression, ridge regression, random forest (300 trees) and XGBoost (400 trees, learning rate 0.05, depth 4), with common default settings. XGBoost was additionally tuned with Optuna (25 trials, grouped cross-validation objective).

*Sequence:* an MLP on the flattened window, a two-layer LSTM and GRU (64 hidden units), and a TCN (four residual blocks, dilations 1–8), on windows of 30 cycles with 28 channels (14 standardised sensors and their change from baseline). All use Adam (learning rate 0.001), batch size 256, mean-squared-error loss and early stopping with patience 8. Each is trained with three seeds. A small Transformer encoder (two layers, width 64) is evaluated in the generalisation study.

### 4.5 Metrics

RMSE, MAE, and the asymmetric score of [1], *s* = Σ (exp(−*d*/13) − 1) for *d* < 0 and Σ (exp(*d*/10) − 1) for *d* ≥ 0, with *d* the predicted minus the true RUL. We use the constants in the form adopted throughout the literature, consistent with the description in [1] that late predictions are penalised more heavily.

### 4.6 Explanation

SHAP values [11] are computed exactly for the XGBoost model with the tree explainer. Because each sensor contributes four related features, attributions are summed per sensor before interpretation.

### 4.7 Uncertainty

Two further XGBoost models are trained for the 5% and 95% conditional quantiles. Following [12], their band is adjusted by a single correction equal to the appropriate quantile of conformity scores, computed on 5-fold out-of-fold predictions by engine. An interval whose upper end reaches the cap is treated as one-sided ("at least").

### 4.8 Multi-condition subsets

For FD002 and FD004, each row is assigned to one of six operating regimes by rounding its settings, and every sensor is standardised within its regime using training-engine statistics. The feature recipe is then applied unchanged, using the 15 sensors that vary in all four subsets.

## 5. Experimental Setup

Experiments were run on a laptop CPU with Python 3.13, scikit-learn 1.9, XGBoost 3.4 and PyTorch 2.15; exact versions are pinned in `requirements.txt`. Random seeds are fixed throughout. Runs in the evaluation study are logged with MLflow. Every table below is regenerated by the named notebook.

## 6. Results

### 6.1 Evaluation choices change the reported error

**Table 2. Effect of the validation split (FD001, gradient-boosted trees, RMSE against the capped target).**

| Features | Random-row 5-fold | Engine-wise 5-fold | Error understated by |
|---|---:|---:|---:|
| Single-cycle readings | 18.14 | 18.70 | 3% |
| History features (rolling, baseline) | 8.88 | 13.48 | 34% |

*Source: notebook 04.*

The more a feature summarises an engine's history, the more similar neighbouring rows become and the larger the leak. Sliding windows overlap even more than these features.

**Table 3. Effect of the RUL cap (FD001, engine-wise CV, RMSE against the uncapped truth).**

| Cap | Rows within 100 cycles of failure | Rows within 150 cycles |
|---|---:|---:|
| None | 32.6 | 32.6 |
| 150 | 26.0 | 24.7 |
| 130 | 22.7 | 22.7 |
| 125 | 21.7 | 22.5 |
| 115 | 19.7 | 22.6 |
| 100 | 16.6 | 24.5 |

*Source: notebook 04 (raw sensor features).*

Caps from 115 to 130 are indistinguishable on the wider set of rows; 125 was adopted.

### 6.2 Model comparison on FD001

**Table 4. FD001 test set (100 engines). Truth as supplied; predictions clipped to [0, 125].**

| Model | Trained on | Seeds | RMSE | MAE | Score |
|---|---|---:|---:|---:|---:|
| Mean predictor | 100 engines | – | 43.1 | 35.9 | 33,629 |
| Linear regression | 100 engines | – | 18.0 | 14.3 | 511 |
| Random forest | 100 engines | 5 | 13.85 ± 0.06 | – | 265 ± 2 |
| XGBoost, default | 100 engines | 5 | 14.78 ± 0.29 | 10.81 ± 0.15 | 305 ± 17 |
| XGBoost, tuned | 100 engines | 5 | 14.42 ± 0.12 | 10.37 ± 0.10 | 296 ± 4 |
| XGBoost, default | 80 engines | 1 | 14.6 | 10.6 | 302 |
| MLP | 80 engines | 3 | 16.27 ± 0.62 | – | 379 ± 33 |
| GRU | 80 engines | 3 | 16.36 ± 0.78 | – | 402 ± 67 |
| TCN | 80 engines | 3 | 16.78 ± 0.66 | – | 422 ± 62 |
| LSTM | 80 engines | 3 | 17.00 ± 0.85 | – | 435 ± 43 |
| MLP, 3-seed ensemble | 80 engines | – | 15.8 | 11.9 | 344 |
| GRU, 3-seed ensemble | 80 engines | – | 16.0 | 11.9 | 375 |
| TCN, 3-seed ensemble | 80 engines | – | 16.3 | 12.0 | 376 |
| LSTM, 3-seed ensemble | 80 engines | – | 16.4 | 12.7 | 387 |

*Sources: notebooks 05, 06 and 07. ± is the standard deviation over seeds.*

Three observations. (i) Tree models on engineered features are at least as accurate as the neural networks. (ii) The four network architectures cannot be separated: their means span 0.7 cycles, less than their seed spread. (iii) On the 20 hold-out engines the networks scored 10.4–11.4 against 12.8 for XGBoost trained on the same 80 engines. That ordering reversed on the test set. The hold-out engines had been used to choose each network's stopping epoch, and 20 engines is a small sample.

For engines within 30 cycles of failure, the MAE of XGBoost is about 3 cycles and that of the networks 4–6. All capped models underestimate the 11 test engines whose true RUL exceeds 125, by about 20 cycles on average.

### 6.3 What the accuracy depends on

**Table 5. Feature ablation (FD001, XGBoost, engine-wise CV RMSE; all features: 13.30 ± 0.74).**

| Feature family | Removed | Used alone |
|---|---:|---:|
| Change from engine baseline | 17.04 | 15.65 |
| 30-cycle rolling standard deviation | 13.67 | 25.59 |
| 30-cycle rolling mean | 13.58 | 22.43 |
| Current reading | 13.41 | 18.65 |

*Source: notebook 07.*

Removing the baseline-relative features costs 3.7 cycles; no other removal exceeds the fold-to-fold spread. The same idea helped every neural network: adding baseline-relative channels lowered hold-out RMSE by 1.3–2.8 cycles (notebook 06). By comparison, 25 trials of hyperparameter search improved test RMSE by 0.36 cycles.

### 6.4 Robustness

Adding Gaussian noise equal in standard deviation to each sensor's healthy noise raises XGBoost's test RMSE from 15.1 to 21.3. Replacing one sensor's last 30 readings with the engine's early-life mean, to imitate a sensor stuck at a healthy value, makes the model more optimistic for every sensor tested (mean estimate +2 to +8 cycles). For sensor 11 (Ps30) the number of engines predicted late by more than 20 cycles rises from 7 to 24. The model gives no indication that an input is faulty. *Source: notebook 07.*

### 6.5 Explanations

By mean absolute SHAP value summed per sensor, the model relies most on sensor 11 (Ps30, 18% of total attribution), sensor 4 (T50, 12%) and sensor 12 (phi, 9%). These are also the three sensors with the highest rank correlation with RUL in the raw data. Baseline-relative features account for 51% of attribution, rolling means 29%, rolling standard deviations 13% and current readings 7%, in agreement with the ablation.

The contribution of the Ps30 baseline-relative feature decreases monotonically as the feature increases (Spearman −0.93), matching the physical trend. The two core-speed sensors (9 and 14), whose direction of change differs between engines, rank fourth and fifth; the model uses sensor 9 only when it has risen substantially above baseline.

Across five models trained on different sets of 80 engines, sensor 11 is ranked first in every case with 17–19% of attribution, while the mean pairwise rank correlation of the full ordering is 0.77 (minimum 0.56). The leading sensors are stable; the detailed ordering is not. *Source: notebook 08.*

These attributions describe the model. They do not establish a physical cause.

### 6.6 Prediction intervals

**Table 6. 90% intervals on FD001 (100 test engines). Coverage against the capped truth.**

| Method | Coverage | Mean width | Coverage, true RUL 61–90 | Width, true RUL ≤ 30 |
|---|---:|---:|---:|---:|
| Constant-width split conformal | 89% | 42.1 | 73% | 41.8 |
| Conformalized quantile regression | 95% | 44.3 | 93% | 26.2 |

*Source: notebook 09.*

Both methods are consistent with the nominal level given the sample size, at similar mean width. The adaptive interval is narrow near failure and widest in mid-life (about 67 cycles for predictions near 82), and 51 of 100 intervals reach the cap. Of the five engines outside their CQR interval, three failed sooner than the lower bound, all with a true RUL of 21 or less. Measured against the uncapped truth, coverage is 84%.

### 6.7 Generalisation

**Table 7. XGBoost with the FD001 recipe on all subsets (untuned).**

| Subset | CV RMSE | Test RMSE | Test RMSE, truth capped | Engines above cap | Interval coverage | Coverage, true RUL ≤ 30 |
|---|---:|---:|---:|---:|---:|---:|
| FD001 | 13.3 ± 0.7 | 14.9 | 13.8 | 11 / 100 | 95.0% | 88% (25 engines) |
| FD002 | 14.2 ± 1.0 | 25.0 | 12.8 | 57 / 259 | 91.5% | 84% (61) |
| FD003 | 12.3 ± 1.1 | 15.5 | 14.0 | 15 / 100 | 89.0% | 100% (20) |
| FD004 | 14.4 ± 2.0 | 26.4 | 14.3 | 67 / 248 | 87.1% | 76% (53) |

*Source: notebook 10. Fifteen common sensors, so FD001 differs slightly from Table 4.*

On the cross-validated and capped-truth measures the pipeline performs similarly on all four subsets. The large uncapped test RMSE on FD002 and FD004 is due to the proportion of test engines beyond the cap. Without regime normalisation, CV RMSE on FD002 is 19.5; supplying the operational settings as additional features does not help (19.5).

Interval coverage is near nominal overall but falls to 84% and 76% for near-failure engines in FD002 and FD004; in FD004, 22 engines failed sooner than their interval allowed.

**Table 8. Test RMSE when a model trained on one subset is applied to another.**

| Trained on ↓ / tested on → | FD001 | FD002 | FD003 | FD004 |
|---|---:|---:|---:|---:|
| FD001 | 14.9 | 30.2 | 23.6 | 32.5 |
| FD002 | 15.6 | 25.0 | 20.7 | 30.8 |
| FD003 | 18.3 | 32.8 | 15.5 | 33.3 |
| FD004 | 16.1 | 29.2 | 18.5 | 26.4 |

*Source: notebook 10. Target-subset sensors are normalised with the target subset's own training statistics (no RUL labels).*

A model moved from six operating conditions to one loses little (FD002→FD001: +0.6). A model that has not seen a fault mode loses much more (FD001→FD003: +8.1). The model trained on the most varied subset, FD004, transfers best.

**Table 9. Neural networks on all subsets (test RMSE; 80% of engines for training).**

| Model | Seeds | FD001 | FD002 | FD003 | FD004 |
|---|---:|---:|---:|---:|---:|
| XGBoost | 1 | 14.4 | 25.1 | 15.9 | 26.7 |
| MLP | 3 | 16.1 ± 0.4 | 25.4 ± 0.4 | 15.0 ± 0.4 | 27.8 ± 0.2 |
| GRU | 1 | 16.7 | 24.0 | 14.7 | 27.0 |
| Transformer | 1 | 16.1 | 24.6 | 18.2 | 27.2 |

*Source: notebook 10.*

No model is best on all subsets. The networks are about one cycle better than XGBoost on FD003 and possibly on FD002, and worse on FD001 and FD004. The Transformer is best on none. Given single seeds for two of the three networks, differences below about two cycles are inconclusive.

## 7. Discussion

**Why did simpler models match deep ones?** On FD001, degradation behaves largely as a single smooth process observed through independent noise. Rolling means average the noise, and baseline-relative features remove engine-to-engine offsets; once these are supplied, little structure remains for a sequence model to discover. The networks were also limited to a 30-cycle window by the shortest test history, whereas the baseline feature reaches back to the first cycles. This is an interpretation consistent with the ablation and with the PCA result, not a tested mechanism.

**The validation set misled.** The networks' apparent advantage on the hold-out engines is the kind of result that is easy to report in good faith. It arose from using a small validation set both to stop training and to compare models. Only the untouched test set corrected it.

**The reported metric depends on the cap.** Table 7 shows the same model at 12.8 and 25.0 on FD002 depending on whether the test truth is capped. Any RUL result should state this choice.

**Coverage is not uniform.** The conformal guarantee is marginal over engines. In our data the misses concentrate among engines close to failure, which is where an interval matters most. Calibrating separately by predicted RUL would be the natural next step.

**Optimism under sensor faults.** A sensor stuck at a healthy value biases every tested model output in the unsafe direction, silently. A deployed system needs sensor validation in front of the model.

**The assistant.** The accompanying system exposes predictions through a question-answering assistant constrained to a fact sheet generated by the model, with a numeric grounding check and a rule-based fallback. It is an engineering component and is not evaluated here.

## 8. Limitations

- All data are simulated by one engine model with artificially added noise. No result has been validated on real engines.
- FD001–FD004 share the same simulator, sensors and engine type; the transfer results say nothing about transfer between real engine types.
- The comparison of tabular and deep models is not exhaustive. Networks were not tuned, used one window length, and were trained on 80% of the engines. On FD002–FD004 two of three networks have a single seed.
- The RUL cap and feature windows were chosen on FD001 and reused elsewhere.
- Test sets contain 100 to 259 engines; differences of under a cycle and coverage differences of a few points are within sampling variation.
- The asymmetric score uses the constants as adopted in the literature; we did not independently confirm their assignment in the original equation.
- The explanation analysis covers one model. Plausibility was judged against the same dataset.
- Robustness was tested with two simple synthetic disturbances.

## 9. Conclusion

On the C-MAPSS benchmark, a gradient-boosted model with a small set of causal, engine-relative features matched or exceeded four neural architectures on FD001 and remained competitive on the three harder subsets after per-regime normalisation. Most of its accuracy comes from expressing each sensor relative to the engine's own early-life level. How results are validated and scored changed the reported error by more than the choice of model did. Conformalized quantile regression gave intervals with close to nominal overall coverage, but with lower coverage near failure on the multi-condition subsets. We suggest that RUL studies report the validation unit, the treatment of the target and test truth, variation over seeds, and coverage by stage of life alongside headline accuracy.

## References

[1] A. Saxena, K. Goebel, D. Simon, and N. Eklund, "Damage propagation modeling for aircraft engine run-to-failure simulation," in *Proc. 1st Int. Conf. on Prognostics and Health Management (PHM08)*, Denver, CO, 2008.

[2] F. O. Heimes, "Recurrent neural networks for remaining useful life estimation," in *Proc. 2008 Int. Conf. on Prognostics and Health Management*, Denver, CO, 2008, pp. 1–6. doi:10.1109/PHM.2008.4711422.

[3] S. Zheng, K. Ristovski, A. Farahat, and C. Gupta, "Long short-term memory network for remaining useful life estimation," in *Proc. 2017 IEEE Int. Conf. on Prognostics and Health Management (ICPHM)*, Dallas, TX, 2017, pp. 88–95.

[4] X. Li, Q. Ding, and J.-Q. Sun, "Remaining useful life estimation in prognostics using deep convolution neural networks," *Reliability Engineering & System Safety*, vol. 172, pp. 1–11, 2018. doi:10.1016/j.ress.2017.11.021.

[5] S. Hochreiter and J. Schmidhuber, "Long short-term memory," *Neural Computation*, vol. 9, no. 8, pp. 1735–1780, 1997.

[6] K. Cho et al., "Learning phrase representations using RNN encoder–decoder for statistical machine translation," in *Proc. EMNLP*, 2014.

[7] S. Bai, J. Z. Kolter, and V. Koltun, "An empirical evaluation of generic convolutional and recurrent networks for sequence modeling," arXiv:1803.01271, 2018.

[8] A. Vaswani et al., "Attention is all you need," in *Advances in Neural Information Processing Systems 30*, 2017.

[9] L. Breiman, "Random forests," *Machine Learning*, vol. 45, no. 1, pp. 5–32, 2001.

[10] T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in *Proc. 22nd ACM SIGKDD Int. Conf. on Knowledge Discovery and Data Mining*, 2016.

[11] S. M. Lundberg and S.-I. Lee, "A unified approach to interpreting model predictions," in *Advances in Neural Information Processing Systems 30*, 2017.

[12] Y. Romano, E. Patterson, and E. J. Candès, "Conformalized quantile regression," in *Advances in Neural Information Processing Systems 32*, 2019.

[13] T. Akiba, S. Sano, T. Yanase, T. Ohta, and M. Koyama, "Optuna: A next-generation hyperparameter optimization framework," in *Proc. 25th ACM SIGKDD Int. Conf. on Knowledge Discovery and Data Mining*, 2019.
