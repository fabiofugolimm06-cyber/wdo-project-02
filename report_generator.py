import yaml

def generate_report(metrics, trades, window_config, output_path):
    report = {
        'validation_window': {
            'train_start': window_config['train_start'],
            'train_end': window_config['train_end'],
            'test_start': window_config['test_start'],
            'test_end': window_config['test_end']
        },
        'metrics': metrics,
        'num_trades': len(trades),
        'trades_summary': {
            'edges_used': list(set([t['edge'] for t in trades])) if trades else []
        }
    }
    with open(output_path, 'w') as f:
        yaml.dump(report, f, default_flow_style=False)
